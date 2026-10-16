import hashlib
import hmac
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Tuple

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from auth.config import AuthSettings

_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"


# ----------------------------------------------------------------------
# Passwords (Argon2id)
# ----------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:

    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ----------------------------------------------------------------------
# Secret key
# ----------------------------------------------------------------------

def jwt_secret(settings: AuthSettings) -> str:
    """JWT_SECRET_KEY, or a random key kept in assets/database/.jwt.key."""

    if settings.JWT_SECRET_KEY:

        if len(settings.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters.")

        return settings.JWT_SECRET_KEY

    key_file = Path("assets/database/.jwt.key")

    if key_file.exists():
        return key_file.read_text().strip()

    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(64)
    key_file.write_text(key)

    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass

    return key


# ----------------------------------------------------------------------
# Access token (JWT)
# ----------------------------------------------------------------------

def create_access_token(settings: AuthSettings, user: dict, now: float = None) -> Tuple[str, int]:

    issued = int(now if now is not None else time.time())
    expires_in = settings.JWT_ACCESS_MINUTES * 60

    payload = {
        "sub": user["id"],
        "role": user["role"],
        "tv": user["token_version"],
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "iat": issued,
        "exp": issued + expires_in,
        "jti": uuid.uuid4().hex,
    }

    return jwt.encode(payload, jwt_secret(settings), algorithm=JWT_ALGORITHM), expires_in


def decode_access_token(settings: AuthSettings, token: str, now: float = None) -> dict:
    """
    Raises jwt.InvalidTokenError for anything that is not a valid access token.

    The signature, issuer and required claims are checked by PyJWT. The
    expiry is checked here against `now` (the service clock) so time can be
    controlled in tests; in production `now` is the real time.
    """

    payload = jwt.decode(
        token,
        jwt_secret(settings),
        algorithms=[JWT_ALGORITHM],          # never trust the token's own "alg"
        issuer=settings.JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "iss", "type"],
                 "verify_exp": False, "verify_iat": False, "verify_nbf": False},
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")

    current = time.time() if now is None else now

    if not isinstance(payload["exp"], (int, float)) or payload["exp"] <= current:
        raise jwt.ExpiredSignatureError("Signature has expired")

    # a token from the future is refused (60 s of tolerance for clock skew)
    if not isinstance(payload["iat"], (int, float)) or payload["iat"] > current + 60:
        raise jwt.InvalidTokenError("issued in the future")

    return payload


# ----------------------------------------------------------------------
# One-time codes and refresh tokens
# ----------------------------------------------------------------------

def generate_otp(length: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(settings: AuthSettings, identifier: str, purpose: str, code: str) -> str:
    """Only a keyed hash of the code is stored."""

    message = f"{purpose}:{identifier}:{code}".encode()

    return hmac.new(jwt_secret(settings).encode(), message, hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    # refresh tokens are 384 random bits, a plain SHA-256 is enough
    return hashlib.sha256(token.encode()).hexdigest()
