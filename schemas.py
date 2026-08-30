from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class FavoriteCreate(BaseModel):
    item_type: str
    item_id: str
    title: str | None = None
    image_url: str | None = None


class FavoriteResponse(BaseModel):
    id: int
    item_type: str
    item_id: str
    title: str | None
    image_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True