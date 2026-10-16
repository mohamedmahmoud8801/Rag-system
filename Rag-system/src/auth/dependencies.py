from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.config import get_auth_settings
from auth.errors import AuthError, to_http
from auth.service import AuthService
from auth.store import get_store

_bearer = HTTPBearer(auto_error=False)


def get_service() -> AuthService:

    settings = get_auth_settings()

    return AuthService(settings, get_store(settings.AUTH_DATABASE_URL))


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    service: AuthService = Depends(get_service),
) -> dict:
    """
    Authentication. Use it on any route or router:

        @router.get("/x")
        def x(user = Depends(get_current_user)): ...

        app.include_router(router, dependencies=[Depends(get_current_user)])
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise to_http(AuthError(401, "missing_token", "Sign in first."))

    try:
        return service.authenticate(credentials.credentials)
    except AuthError as error:
        raise to_http(error)


def require_roles(*roles: str):
    """
    Authorization:  Depends(require_roles("admin"))
    """

    def check(user: dict = Depends(get_current_user)) -> dict:

        if user["role"] not in roles:
            raise to_http(AuthError(403, "forbidden", "You do not have permission for this action."))

        return user

    return check
