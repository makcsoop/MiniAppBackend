# app/routers/payment.py
import hmac
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db_session, get_current_user
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])

def get_payment_service(db: AsyncSession = Depends(get_db_session)) -> PaymentService:
    return PaymentService(db=db)

@router.post("/create", response_model=PaymentResponse)
async def create_payment(
     PaymentCreate,
    service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user)
):
    try:
        payment, url = await service.create_payment(current_user.id, data.booking_id, data.amount, data.method)
        return PaymentResponse(
            payment_id=payment.id, status=payment.status.value, 
            confirmation_url=url, yookassa_payment_id=payment.yookassa_payment_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@router.post("/webhook")
async def yookassa_webhook(
    request: Request,
    x_hmac: str = Header(None, alias="Content-HMAC-SHA256"),
    service: PaymentService = Depends(get_payment_service)
):
    body = await request.body()
    
    # В тестовом режиме ЮKassa может не присылать подпись
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