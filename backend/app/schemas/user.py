from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.user import UserRole

class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: bool
    role: UserRole
    created_at: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)