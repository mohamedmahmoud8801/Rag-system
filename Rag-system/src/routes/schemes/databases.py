from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class ConnectionParams(BaseModel):
    """Fields of the Connect database form."""

    # "postgresql" or "sqlite"
    provider: str

    # PostgreSQL
    host: Optional[str] = None
    port: int = Field(default=5432, ge=1, le=65535)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    ssl: bool = False

    # SQLite: the NAME of a file inside the server's allowed folder
    file: Optional[str] = None

    def to_params(self) -> dict:

        data = self.model_dump() if hasattr(self, "model_dump") else self.dict()

        data["password"] = (
            self.password.get_secret_value() if self.password else ""
        )

        return data


class ConnectionCreateRequest(ConnectionParams):
    name: str = Field(..., min_length=1, max_length=80)