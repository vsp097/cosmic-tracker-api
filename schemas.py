from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Registro. Exige una contraseña mínima para no crear cuentas triviales."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """
    Login con JSON.

    Es un esquema aparte del de registro a propósito: si el login heredara el
    `min_length` de `UserCreate`, una cuenta vieja con contraseña corta
    recibiría un 422 de validación en vez de un 401 de credenciales, lo cual
    además filtra información sobre la contraseña almacenada.
    """

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str


class FavoriteCreate(BaseModel):
    item_type: str = Field(min_length=1, max_length=50)
    item_id: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    image_url: str | None = Field(default=None, max_length=1000)


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_type: str
    item_id: str
    title: str | None
    image_url: str | None
    created_at: datetime
