from typing import Literal, Optional

from pydantic import BaseModel, Field, SecretStr


class RegisterRequest(BaseModel):
    # an email (e.g. a Gmail address) or a phone number
    identifier: str = Field(..., min_length=3, max_length=320)
    password: SecretStr
    name: Optional[str] = Field(default=None, max_length=120)


class IdentifierRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=320)


class VerifyRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=320)
    code: str = Field(..., min_length=4, max_length=10)


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=320)
    password: SecretStr


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=320)
    code: str = Field(..., min_length=4, max_length=10)
    new_password: SecretStr


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr


class AdminUserUpdate(BaseModel):
    role: Optional[Literal["user", "admin"]] = None
    is_active: Optional[bool] = None
