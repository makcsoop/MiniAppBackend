# app/models/car.py
from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models import Base

class CarBrand(Base):
    __tablename__ = "car_brands"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    
    # 👇 ИСПРАВЛЕНО: added server_default для created_at, nullable=True + server_default для updated_at
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        onupdate=func.now(), 
        nullable=True,  # 👈 Разрешаем NULL при INSERT
        server_default=func.now()  # 👈 Или задаём дефолтное значение в БД
    )
    
    models = relationship("CarModel", back_populates="brand", cascade="all, delete-orphan")

class CarModel(Base):
    __tablename__ = "car_models"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("car_brands.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # 👇 То же исправление для created_at
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    brand = relationship("CarBrand", back_populates="models")