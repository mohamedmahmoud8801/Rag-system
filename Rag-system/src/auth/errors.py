from typing import Optional

from fastapi import HTTPException


class AuthError(Exception):

    def __init__(self, status: int, code: str, message: str, retry_after: Optional[int] = None):

        super().__init__(message)

        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def to_http(error: AuthError) -> HTTPException:
    """The API always answers {"detail": {"code": ..., "message": ...}}: the UI translates `code`."""

    headers = {}

    if error.retry_after:
        headers["Retry-After"] = str(int(error.retry_after))

    if error.status == 401:
        headers["WWW-Authenticate"] = "Bearer"

    return HTTPException(
        status_code=error.status,
        detail={"code": error.code, "message": error.message},
        headers=headers or None,
    )
