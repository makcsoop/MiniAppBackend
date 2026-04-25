# app/models/__init__.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# 👇 ВАЖНО: Без этой строки Alembin не увидит таблицу users!
from .user import User
from .category import Category
from .product import Product
from .booking import Booking