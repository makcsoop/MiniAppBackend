# app/schemas/car.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CarBrandBase(BaseModel):
    name: str
    slug: str

class CarBrandCreate(CarBrandBase): pass
class CarBrandUpdate(CarBrandBase): pass

class CarBrandResponse(CarBrandBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

class CarModelBase(BaseModel):
    name: str
    slug: str
    brand_id: int

class CarModelCreate(CarModelBase): pass
class CarModelUpdate(CarModelBase): pass

class CarModelResponse(CarModelBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime