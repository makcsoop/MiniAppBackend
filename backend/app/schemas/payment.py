# app/schemas/payment.py
from pydantic import BaseModel, Field

class PaymentCreate(BaseModel):
    booking_id: int = Field(..., description="ID брони для оплаты")
    amount: float = Field(..., gt=0, description="Сумма в рублях")
    method: str = Field("sbp", description="sbp или bank_card")

class PaymentResponse(BaseModel):
    payment_id: int
    status: str
    confirmation_url: str
    yookassa_payment_id: str | None = None