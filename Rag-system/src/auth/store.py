import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, Integer, MetaData, String, Table,
    create_engine, delete, func, insert, select, update,
)
from sqlalchemy.engine import make_url

metadata = MetaData()

users = Table(
    "auth_users", metadata,
    Column("id", String(32), primary_key=True),
    Column("email", String(320), unique=True, nullable=True),
    Column("phone", String(20), unique=True, nullable=True),
    Column("name", String(120), nullable=True),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(20), nullable=False, default="user"),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("email_verified", Boolean, nullable=False, default=False),
    Column("phone_verified", Boolean, nullable=False, default=False),
    Column("failed_logins", Integer, nullable=False, default=0),
    Column("locked_until", BigInteger, nullable=False, default=0),
    # raising it signs out every access token of the user at once
    Column("token_version", Integer, nullable=False, default=0),
    Column("created_at", BigInteger, nullable=False),
    Column("last_login_at", BigInteger, nullable=True),
)

otp_codes = Table(
    "auth_otp_codes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("identifier", String(320), nullable=False, index=True),
    Column("purpose", String(20), nullable=False),
    Column("code_hash", String(64), nullable=False),
    Column("expires_at", BigInteger, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("consumed", Boolean, nullable=False, default=False),
    Column("created_at", BigInteger, nullable=False),
)

refresh_tokens = Table(
    "auth_refresh_tokens", metadata,
    Column("id", String(32), primary_key=True),
    Column("user_id", String(32), nullable=False, index=True),
    Column("family_id", String(32), nullable=False, index=True),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("expires_at", BigInteger, nullable=False),
    Column("used", Boolean, nullable=False, default=False),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("created_at", BigInteger, nullable=False),
)


def _row(row) -> Optional[Dict[str, Any]]:
    return dict(row._mapping) if row is not None else None


class AuthStore:

    def __init__(self, database_url: str):

        url = make_url(database_url)
        kwargs: Dict[str, Any] = {"future": True, "pool_pre_ping": True}

        if url.get_backend_name() == "sqlite":

            if url.database and url.database != ":memory:":
                Path(url.database).parent.mkdir(parents=True, exist_ok=True)

            kwargs["connect_args"] = {"check_same_thread": False}

        self.engine = create_engine(database_url, **kwargs)
        metadata.create_all(self.engine)

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------

    def create_user(self, now: int, **fields) -> Dict[str, Any]:

        user_id = uuid.uuid4().hex

        with self.engine.begin() as c:
            c.execute(insert(users).values(id=user_id, created_at=now, token_version=0,
                                           failed_logins=0, locked_until=0, is_active=True, **fields))

        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:

        with self.engine.begin() as c:
            return _row(c.execute(select(users).where(users.c.id == user_id)).first())

    def find_user(self, kind: str, value: str) -> Optional[Dict[str, Any]]:

        column = users.c.email if kind == "email" else users.c.phone

        with self.engine.begin() as c:
            return _row(c.execute(select(users).where(column == value)).first())

    def update_user(self, user_id: str, **fields) -> None:

        with self.engine.begin() as c:
            c.execute(update(users).where(users.c.id == user_id).values(**fields))

    def bump_token_version(self, user_id: str) -> None:

        with self.engine.begin() as c:
            c.execute(update(users).where(users.c.id == user_id)
                      .values(token_version=users.c.token_version + 1))

    def list_users(self, limit: int, offset: int) -> List[Dict[str, Any]]:

        with self.engine.begin() as c:
            rows = c.execute(select(users).order_by(users.c.created_at).limit(limit).offset(offset)).all()

        return [_row(r) for r in rows]

    # ------------------------------------------------------------------
    # one-time codes
    # ------------------------------------------------------------------

    def create_otp(self, identifier: str, purpose: str, code_hash: str, expires_at: int, now: int) -> None:

        with self.engine.begin() as c:
            # old, long-expired codes are removed on the way
            c.execute(delete(otp_codes).where(otp_codes.c.expires_at < now - 86400))
            c.execute(insert(otp_codes).values(identifier=identifier, purpose=purpose, code_hash=code_hash,
                                               expires_at=expires_at, attempts=0, consumed=False, created_at=now))

    def active_otp(self, identifier: str, purpose: str, now: int) -> Optional[Dict[str, Any]]:

        q = (select(otp_codes)
             .where(otp_codes.c.identifier == identifier, otp_codes.c.purpose == purpose,
                    otp_codes.c.consumed.is_(False), otp_codes.c.expires_at > now)
             .order_by(otp_codes.c.id.desc()).limit(1))

        with self.engine.begin() as c:
            return _row(c.execute(q).first())

    def bump_otp_attempts(self, otp_id: int) -> None:

        with self.engine.begin() as c:
            c.execute(update(otp_codes).where(otp_codes.c.id == otp_id)
                      .values(attempts=otp_codes.c.attempts + 1))

    def consume_otp(self, otp_id: int) -> bool:
        """True only for the one caller that really consumed it (single use)."""

        with self.engine.begin() as c:
            result = c.execute(update(otp_codes)
                               .where(otp_codes.c.id == otp_id, otp_codes.c.consumed.is_(False))
                               .values(consumed=True))

        return result.rowcount == 1

    def invalidate_otps(self, identifier: str, purpose: str) -> None:

        with self.engine.begin() as c:
            c.execute(update(otp_codes)
                      .where(otp_codes.c.identifier == identifier, otp_codes.c.purpose == purpose,
                             otp_codes.c.consumed.is_(False))
                      .values(consumed=True))

    def delete_active_otps(self, identifier: str, purpose: str) -> None:
        """Used when the code could not be delivered: it never existed for the user."""

        with self.engine.begin() as c:
            c.execute(delete(otp_codes).where(otp_codes.c.identifier == identifier,
                                              otp_codes.c.purpose == purpose,
                                              otp_codes.c.consumed.is_(False)))

    def last_otp_created(self, identifier: str, purpose: str) -> Optional[int]:

        with self.engine.begin() as c:
            return c.execute(select(func.max(otp_codes.c.created_at))
                             .where(otp_codes.c.identifier == identifier,
                                    otp_codes.c.purpose == purpose)).scalar()

    def count_otps_since(self, identifier: str, purpose: str, since: int) -> int:

        with self.engine.begin() as c:
            return c.execute(select(func.count()).select_from(otp_codes)
                             .where(otp_codes.c.identifier == identifier, otp_codes.c.purpose == purpose,
                                    otp_codes.c.created_at >= since)).scalar()

    # ------------------------------------------------------------------
    # refresh tokens
    # ------------------------------------------------------------------

    def create_refresh(self, user_id: str, family_id: str, token_hash: str, expires_at: int, now: int) -> None:

        with self.engine.begin() as c:
            c.execute(delete(refresh_tokens).where(refresh_tokens.c.expires_at < now - 86400))
            c.execute(insert(refresh_tokens).values(
                id=uuid.uuid4().hex, user_id=user_id, family_id=family_id, token_hash=token_hash,
                expires_at=expires_at, used=False, revoked=False, created_at=now))

    def find_refresh(self, token_hash: str) -> Optional[Dict[str, Any]]:

        with self.engine.begin() as c:
            return _row(c.execute(select(refresh_tokens)
                                  .where(refresh_tokens.c.token_hash == token_hash)).first())

    def mark_refresh_used(self, refresh_id: str) -> bool:
        """Atomic: two requests with the same token cannot both succeed."""

        with self.engine.begin() as c:
            result = c.execute(update(refresh_tokens)
                               .where(refresh_tokens.c.id == refresh_id, refresh_tokens.c.used.is_(False),
                                      refresh_tokens.c.revoked.is_(False))
                               .values(used=True))

        return result.rowcount == 1

    def revoke_family(self, family_id: str) -> None:

        with self.engine.begin() as c:
            c.execute(update(refresh_tokens).where(refresh_tokens.c.family_id == family_id)
                      .values(revoked=True))

    def revoke_user_tokens(self, user_id: str) -> None:

        with self.engine.begin() as c:
            c.execute(update(refresh_tokens).where(refresh_tokens.c.user_id == user_id)
                      .values(revoked=True))


_stores: Dict[str, AuthStore] = {}


def get_store(database_url: str) -> AuthStore:

    if database_url not in _stores:
        _stores[database_url] = AuthStore(database_url)

    return _stores[database_url]
