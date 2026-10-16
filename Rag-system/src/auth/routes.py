from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import get_current_user, get_service, require_roles
from auth.errors import AuthError, to_http
from auth.ratelimit import rate_limit
from auth.schemas import (
    AdminUserUpdate, ChangePasswordRequest, IdentifierRequest, LoginRequest,
    RefreshRequest, RegisterRequest, ResetPasswordRequest, VerifyRequest,
)
from auth.service import AuthService

auth_router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
    dependencies=[Depends(rate_limit)],
)


def _run(function, *args, **kwargs):

    try:
        return function(*args, **kwargs)
    except AuthError as error:
        raise to_http(error)


# ---------------------------------------------------------------- sign-up

@auth_router.post("/register", status_code=201)
def register(body: RegisterRequest, service: AuthService = Depends(get_service)):
    """Create an account with an email or a phone number. A code is sent."""

    return _run(service.register, body.identifier, body.password.get_secret_value(), body.name)


@auth_router.post("/verify")
def verify(body: VerifyRequest, service: AuthService = Depends(get_service)):
    """Confirm the code: the account is verified and you are signed in."""

    return _run(service.verify, body.identifier, body.code)


@auth_router.post("/resend")
def resend(body: IdentifierRequest, service: AuthService = Depends(get_service)):
    """Send the verification code again."""

    return _run(service.resend, body.identifier)


# ---------------------------------------------------------------- sign-in

@auth_router.post("/login")
def login(body: LoginRequest, service: AuthService = Depends(get_service)):
    """Email or phone + password."""

    return _run(service.login, body.identifier, body.password.get_secret_value())


@auth_router.post("/login/code/request")
def request_login_code(body: IdentifierRequest, service: AuthService = Depends(get_service)):
    """Sign in WITHOUT a password: a code is sent to the email or phone."""

    return _run(service.request_login_code, body.identifier)


@auth_router.post("/login/code/verify")
def login_with_code(body: VerifyRequest, service: AuthService = Depends(get_service)):

    return _run(service.login_with_code, body.identifier, body.code)


@auth_router.post("/refresh")
def refresh(body: RefreshRequest, service: AuthService = Depends(get_service)):
    """New access token + new refresh token (the old refresh token stops working)."""

    return _run(service.refresh, body.refresh_token)


@auth_router.post("/logout")
def logout(body: RefreshRequest, service: AuthService = Depends(get_service)):

    return _run(service.logout, body.refresh_token)


@auth_router.post("/logout-all")
def logout_all(user: dict = Depends(get_current_user), service: AuthService = Depends(get_service)):

    return _run(service.logout_all, user["id"])


# ---------------------------------------------------------------- passwords

@auth_router.post("/password/forgot")
def forgot_password(body: IdentifierRequest, service: AuthService = Depends(get_service)):
    """Always answers the same, whether the account exists or not."""

    return _run(service.forgot_password, body.identifier)


@auth_router.post("/password/reset")
def reset_password(body: ResetPasswordRequest, service: AuthService = Depends(get_service)):

    return _run(service.reset_password, body.identifier, body.code, body.new_password.get_secret_value())


@auth_router.post("/password/change")
def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    service: AuthService = Depends(get_service),
):

    return _run(service.change_password, user["id"],
                body.current_password.get_secret_value(), body.new_password.get_secret_value())


# ---------------------------------------------------------------- me / admin

@auth_router.get("/me")
def me(user: dict = Depends(get_current_user)):

    return {"user": user}


@auth_router.get("/users")
def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(require_roles("admin")),
    service: AuthService = Depends(get_service),
):
    """Admins only."""

    return {"users": service.list_users(limit, offset)}


@auth_router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: dict = Depends(require_roles("admin")),
    service: AuthService = Depends(get_service),
):
    """Admins only: change a role or disable an account."""

    return {"user": _run(service.update_user, admin["id"], user_id, body.role, body.is_active)}
