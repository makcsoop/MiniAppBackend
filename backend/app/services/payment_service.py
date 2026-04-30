# app/services/payment_service.py
import uuid
import asyncio
from typing import Optional, Tuple
from yookassa import Configuration, Payment as YooKassaPayment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.config import settings

# Инициализация SDK
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(self, user_id: int, booking_id: int, amount: float, method: str = "sbp") -> Tuple[Payment, str]:
        # Идемпотентность
        idem_key = str(uuid.uuid4())
        
        payment = Payment(
            user_id=user_id, booking_id=booking_id, amount=amount,
            currency="RUB", idempotency_key=idem_key,
            payment_method=PaymentMethod.SBP if method == "sbp" else PaymentMethod.BANK_CARD
        )
        self.db.add(payment)
        await self.db.flush()

        # Подготовка данных для ЮKassa
        yoo_payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": settings.YOOKASSA_RETURN_URL},
            "capture": True,
            "description": f"Оплата брони #{booking_id}",
            "idempotency_key": idem_key
        }
        if method == "sbp":
            yoo_payload["payment_method_data"] = {"type": "sbp"}

        # ЮKassa SDK синхронный → запускаем в пуле потоков
        async def _call_yookassa():
            return YooKassaPayment.create(yoo_payload)

        yoo_res = await asyncio.to_thread(_call_yookassa)
        
        payment.yookassa_payment_id = yoo_res.id
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment, yoo_res.confirmation["confirmation_url"]

    async def process_webhook(self, event: dict) -> Optional[Payment]:
        yoo_id = event.get("object", {}).get("id")
        status_raw = event.get("event", event.get("object", {}).get("status"))
        
        status_map = {"payment.succeeded": PaymentStatus.SUCCEEDED, "payment.canceled": PaymentStatus.CANCELED}
        status = status_map.get(status_raw)
        if not status or not yoo_id: return None

        stmt = select(Payment).where(Payment.yookassa_payment_id == yoo_id)
        result = await self.db.execute(stmt)
        payment = result.scalars().first()
        
        if not payment or payment.status == status: return payment

        payment.status = status
        await self.db.commit()
        return payment