# backend/app/models/__init__.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# 👇 Импортируем ВСЕ модели (иначе Alembic их не увидит)
from .user import User
from .category import Category
from .product import Product
from .booking import Booking
from .payment import Payment

__all__ = ["Base", "User", "Category", "Product", "Booking", "Payment"]