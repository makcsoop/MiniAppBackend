# app/schemas/payment.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal


class PaymentCreate(BaseModel):
    """Схема для создания платежа"""
    booking_id: int = Field(..., gt=0, description="ID брони для оплаты", examples=[1])
    amount: float = Field(..., gt=0, description="Сумма в рублях", examples=[35000.00])
    method: Literal["sbp", "bank_card"] = Field(default="sbp", description="Метод оплаты", examples=["sbp"])
    description: Optional[str] = Field(None, description="Описание платежа", examples=["Оплата брони #1"])


class PaymentResponse(BaseModel):
    """Схема ответа после создания платежа"""
    payment_id: int = Field(..., description="Внутренний ID платежа")
    status: str = Field(..., description="Статус платежа", examples=["pending", "succeeded", "canceled"])
    confirmation_url: str = Field(..., description="Ссылка на страницу оплаты ЮKassa")
    yookassa_payment_id: Optional[str] = Field(None, description="ID платежа в системе ЮKassa")
    
    # Разрешаем конвертацию из SQLAlchemy-моделей
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "payment_id": 1,
                "status": "pending",
                "confirmation_url": "https://yookassa.ru/checkout/v1/...",
                "yookassa_payment_id": "2d3d4f5a-8b9c-1d2e-3f4a-5b6c7d8e9f0a"
            }
        }
    )