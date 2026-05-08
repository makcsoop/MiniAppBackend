# app/routers/payment.py
import hmac
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_current_user
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import PaymentService
from app.config import settings  # 👈 Добавьте этот импорт для webhook

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_payment_service(db: AsyncSession = Depends(get_db_session)) -> PaymentService:
    return PaymentService(db=db)


# 👇 КЛЮЧЕВОЕ: символ @ перед декоратором
@router.post("/create", response_model=PaymentResponse, summary="Создать платёж")
async def create_payment(
    data: PaymentCreate = Body(..., embed=True),  # 👈 embed=True помогает Swagger
    service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user)
):
    """
    Создать платёж для бронирования через ЮKassa.
    
    - **booking_id**: ID существующей брони со статусом `pending`
    - **amount**: Сумма должна точно совпадать с ценой услуги
    - **method**: `sbp` (СБП) или `bank_card`
    
    Возвращает ссылку для перехода на страницу оплаты.
    """
    try:
        payment, url = await service.create_payment(
            current_user.id, 
            data.booking_id, 
            data.amount, 
            data.method
        )
        return PaymentResponse(
            payment_id=payment.id, 
            status=payment.status.value, 
            confirmation_url=url, 
            yookassa_payment_id=payment.yookassa_payment_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Payment service error: {str(e)}")


@router.post("/webhook", summary="Вебхук от ЮKassa")
async def yookassa_webhook(
    request: Request,
    x_hmac: str = Header(None, alias="Content-HMAC-SHA256"),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Эндпоинт для приёма уведомлений от ЮKassa.
    
    Не вызывайте вручную — используется только платежным шлюзом.
    """
    body = await request.body()
    
    if x_hmac and settings.YOOKASSA_WEBHOOK_SECRET:
        expected = hmac.new(
            settings.YOOKASSA_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hmac):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        event = json.loads(body)
        updated = await service.process_webhook(event)
        return {"status": "ok", "payment_id": updated.id if updated else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))