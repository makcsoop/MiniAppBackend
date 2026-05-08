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
            user_id=user_id, 
            booking_id=booking_id, 
            amount=amount,
            currency="RUB", 
            idempotency_key=idem_key,
            payment_method=PaymentMethod.SBP if method == "sbp" else PaymentMethod.BANK_CARD,
            status=PaymentStatus.PENDING  # 👈 Явно задаём статус
        )
        self.db.add(payment)
        await self.db.flush()

        # Подготовка данных для ЮKassa
        yoo_payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": settings.YOOKASSA_RETURN_URL},
            "capture": True,
            "description": f"Оплата брони #{booking_id}",
            "idempotency_key": idem_key,
            "metadata": {
                "booking_id": str(booking_id),
                "user_id": str(user_id)
            }
        }
        if method == "sbp":
            yoo_payload["payment_method_data"] = {"type": "sbp"}

        # ✅ ИСПРАВЛЕНИЕ 1: Передаём синхронный метод напрямую
        # asyncio.to_thread НЕ принимает async def, только обычные функции
        yoo_res = await asyncio.to_thread(YooKassaPayment.create, yoo_payload)
        
        payment.yookassa_payment_id = yoo_res.id
        # ✅ ИСПРАВЛЕНИЕ 2: Доступ к атрибуту через точку, а не через []
        payment.yookassa_confirmation_url = yoo_res.confirmation.confirmation_url
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment, payment.yookassa_confirmation_url

    async def process_webhook(self, event: dict) -> Optional[Payment]:
        yoo_id = event.get("object", {}).get("id")
        # Статус всегда лежит внутри object
        status_raw = event.get("object", {}).get("status")
        
        status_map = {
            "pending": PaymentStatus.PENDING,
            "succeeded": PaymentStatus.SUCCEEDED, 
            "canceled": PaymentStatus.CANCELED,
            "failed": PaymentStatus.FAILED
        }
        new_status = status_map.get(status_raw)
        if not new_status or not yoo_id: 
            return None

        stmt = select(Payment).where(Payment.yookassa_payment_id == yoo_id)
        result = await self.db.execute(stmt)
        payment = result.scalars().first()
        
        if not payment or payment.status == new_status: 
            return payment

        payment.status = new_status
        
        # 👇 Если оплата прошла — подтверждаем бронь
        if new_status == PaymentStatus.SUCCEEDED and payment.booking:
            from app.models.booking import BookingStatus
            payment.booking.status = BookingStatus.CONFIRMED

        await self.db.commit()
        return payment