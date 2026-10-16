import secrets
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import jwt
import phonenumbers
from sqlalchemy.exc import IntegrityError
from email_validator import EmailNotValidError, validate_email
from phonenumbers import NumberParseException, PhoneNumberFormat

from auth import security
from auth.config import AuthSettings
from auth.errors import AuthError
from auth.senders import DeliveryError, build_senders
from auth.store import AuthStore

GENERIC_CODE_SENT = "If the account exists, a code was sent."

COMMON_PASSWORDS = {
    "password", "password1", "12345678", "123456789", "1234567890", "qwertyui",
    "qwerty123", "iloveyou", "11111111", "abcd1234", "admin123", "letmein1",
    "welcome1", "00000000", "password123", "12341234", "987654321",
}

_DUMMY_HASH = security.hash_password("timing-equalizer-password")


class AuthService:
    """All the rules of sign-up, sign-in, codes, passwords and tokens."""

    def __init__(
        self,
        settings: AuthSettings,
        store: AuthStore,
        senders: Optional[Dict[str, Any]] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self.store = store
        self._senders = senders
        self._clock = clock

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _now(self) -> int:
        return int(self._clock())

    @property
    def senders(self) -> Dict[str, Any]:

        if self._senders is None:
            try:
                self._senders = build_senders(self.settings)
            except DeliveryError as exc:
                raise AuthError(500, "delivery_not_configured", str(exc))

        return self._senders

    def normalize_identifier(self, raw: str) -> Tuple[str, str]:
        """("email", "a@b.com") or ("phone", "+201012345678")."""

        raw = (raw or "").strip()

        if not raw:
            raise AuthError(400, "invalid_identifier", "Enter an email or a phone number.")

        if "@" in raw:
            try:
                return "email", validate_email(raw, check_deliverability=False).normalized.lower()
            except EmailNotValidError:
                raise AuthError(400, "invalid_email", "Invalid email address.")

        try:
            number = phonenumbers.parse(raw, self.settings.AUTH_DEFAULT_REGION)
        except NumberParseException:
            raise AuthError(400, "invalid_phone", "Invalid phone number.")

        if not phonenumbers.is_valid_number(number):
            raise AuthError(400, "invalid_phone", "Invalid phone number.")

        return "phone", phonenumbers.format_number(number, PhoneNumberFormat.E164)

    def _admin_identifiers(self) -> set:

        admins = set()

        for item in (self.settings.AUTH_ADMIN_IDENTIFIERS or "").split(","):
            item = item.strip()

            if not item:
                continue

            try:
                admins.add(self.normalize_identifier(item)[1])
            except AuthError:
                continue

        return admins

    def _check_password(self, password: str, identifier: str) -> None:

        minimum = self.settings.AUTH_PASSWORD_MIN_LENGTH

        if len(password) < minimum:
            raise AuthError(400, "weak_password", f"Password must be at least {minimum} characters.")

        if len(password) > 128:
            raise AuthError(400, "weak_password", "Password is too long (max 128 characters).")

        if password.isdigit():
            raise AuthError(400, "weak_password", "Password cannot be only digits.")

        if password.lower() in COMMON_PASSWORDS or password.lower() == identifier.lower() \
                or password.lower() == identifier.split("@")[0].lower():
            raise AuthError(400, "weak_password", "This password is too easy to guess.")

    @staticmethod
    def _verified(user: Dict[str, Any], kind: str) -> bool:
        return bool(user["email_verified"] if kind == "email" else user["phone_verified"])

    @staticmethod
    def public_user(user: Dict[str, Any]) -> Dict[str, Any]:

        return {
            "id": user["id"],
            "email": user["email"],
            "phone": user["phone"],
            "name": user["name"],
            "role": user["role"],
            "email_verified": bool(user["email_verified"]),
            "phone_verified": bool(user["phone_verified"]),
            "is_active": bool(user["is_active"]),
            "created_at": user["created_at"],
        }

    # ------------------------------------------------------------------
    # one-time codes
    # ------------------------------------------------------------------

    def _send_code(self, kind: str, value: str, purpose: str, deliver: bool = True) -> None:
        """
        deliver=False is used for identifiers that have no account: the code
        is "created" but never sent, so the cooldown and the hourly limit
        behave exactly the same and nobody can tell the account does not exist.
        """

        s, now = self.settings, self._now()

        last = self.store.last_otp_created(value, purpose)

        if last is not None and now - last < s.AUTH_OTP_RESEND_SECONDS:
            wait = s.AUTH_OTP_RESEND_SECONDS - (now - last)
            raise AuthError(429, "wait_before_resend", f"Wait {wait} seconds before asking for another code.", wait)

        if self.store.count_otps_since(value, purpose, now - 3600) >= s.AUTH_OTP_MAX_PER_HOUR:
            raise AuthError(429, "too_many_codes", "Too many codes requested. Try again later.", 3600)

        code = security.generate_otp(s.AUTH_OTP_LENGTH)

        self.store.invalidate_otps(value, purpose)
        self.store.create_otp(value, purpose, security.hash_otp(s, value, purpose, code),
                              now + s.AUTH_OTP_MINUTES * 60, now)

        if not deliver:
            return

        subject, body = self._message(purpose, code)

        try:
            self.senders[kind].send(value, subject, body)
        except DeliveryError:
            self.store.delete_active_otps(value, purpose)
            raise AuthError(502, "delivery_failed", "We could not send the code. Try again later.")

    def _message(self, purpose: str, code: str) -> Tuple[str, str]:

        minutes = self.settings.AUTH_OTP_MINUTES

        titles = {
            "verify": "تأكيد حسابك | Verify your account",
            "login": "رمز تسجيل الدخول | Your sign-in code",
            "reset": "إعادة تعيين كلمة المرور | Reset your password",
        }

        body = (
            f"رمز التحقق الخاص بك: {code}\n"
            f"صالح لمدة {minutes} دقائق. لا تشاركه مع أي شخص.\n\n"
            f"Your verification code: {code}\n"
            f"Valid for {minutes} minutes. Never share it with anyone."
        )

        return titles[purpose], body

    def _check_code(self, value: str, purpose: str, code: str) -> None:

        s, now = self.settings, self._now()

        otp = self.store.active_otp(value, purpose, now)

        if otp is None:
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

        if otp["attempts"] >= s.AUTH_OTP_MAX_ATTEMPTS:
            raise AuthError(429, "too_many_attempts", "Too many wrong attempts. Ask for a new code.")

        expected = otp["code_hash"]
        given = security.hash_otp(s, value, purpose, (code or "").strip())

        if not secrets.compare_digest(expected, given):
            self.store.bump_otp_attempts(otp["id"])
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

        if not self.store.consume_otp(otp["id"]):
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

    # ------------------------------------------------------------------
    # tokens
    # ------------------------------------------------------------------

    def _issue_tokens(self, user: Dict[str, Any], family_id: Optional[str] = None) -> Dict[str, Any]:

        s, now = self.settings, self._now()

        access, expires_in = security.create_access_token(s, user, now=now)
        refresh = security.new_refresh_token()

        self.store.create_refresh(
            user_id=user["id"],
            family_id=family_id or secrets.token_hex(16),
            token_hash=security.hash_token(refresh),
            expires_at=now + s.JWT_REFRESH_DAYS * 86400,
            now=now,
        )

        return {
            "access_token": access,
            "token_type": "bearer",
            "expires_in": expires_in,
            "refresh_token": refresh,
            "user": self.public_user(user),
        }

    def authenticate(self, token: str) -> Dict[str, Any]:
        """The user behind a valid access token (used by the route dependency)."""

        try:
            payload = security.decode_access_token(self.settings, token, now=self._now())
        except jwt.ExpiredSignatureError:
            raise AuthError(401, "token_expired", "The access token expired.")
        except jwt.InvalidTokenError:
            raise AuthError(401, "invalid_token", "Invalid access token.")

        user = self.store.get_user(payload["sub"])

        if user is None or not user["is_active"] or payload.get("tv") != user["token_version"]:
            raise AuthError(401, "invalid_token", "Invalid access token.")

        return self.public_user(user)

    # ------------------------------------------------------------------
    # sign-up
    # ------------------------------------------------------------------

    def register(self, identifier: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        self._check_password(password, value)

        existing = self.store.find_user(kind, value)

        if existing is not None and self._verified(existing, kind):
            raise AuthError(409, "already_registered", "This account already exists. Sign in instead.")

        fields = {"name": (name or "").strip() or None, "password_hash": security.hash_password(password)}

        if existing is None:

            try:
                self.store.create_user(
                    self._now(),
                    email=value if kind == "email" else None,
                    phone=value if kind == "phone" else None,
                    role="admin" if value in self._admin_identifiers() else "user",
                    email_verified=False, phone_verified=False, **fields,
                )

            except IntegrityError:
                # someone signed up with the same identifier at the same
                # instant: the database's unique index stopped the second row
                existing = self.store.find_user(kind, value)

                if existing is None:
                    raise AuthError(503, "try_again", "Please try again.")

                if self._verified(existing, kind):
                    raise AuthError(409, "already_registered", "This account already exists. Sign in instead.")

                self.store.update_user(existing["id"], **fields)

        else:
            # an unverified sign-up can be repeated: whoever proves the
            # identifier with the code owns the account (and its password)
            self.store.update_user(existing["id"], **fields)

        self._send_code(kind, value, "verify")

        return {"message": "A verification code was sent.", "identifier": value, "kind": kind,
                "expires_in": self.settings.AUTH_OTP_MINUTES * 60}

    def verify(self, identifier: str, code: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        self._check_code(value, "verify", code)

        user = self.store.find_user(kind, value)

        if user is None:
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

        self.store.update_user(user["id"], **{f"{kind}_verified": True})

        return self._issue_tokens(self.store.get_user(user["id"]))

    def resend(self, identifier: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        user = self.store.find_user(kind, value)

        self._send_code(kind, value, "verify",
                        deliver=user is not None and not self._verified(user, kind))

        return {"message": GENERIC_CODE_SENT}

    # ------------------------------------------------------------------
    # sign-in
    # ------------------------------------------------------------------

    def login(self, identifier: str, password: str) -> Dict[str, Any]:

        s, now = self.settings, self._now()

        kind, value = self.normalize_identifier(identifier)

        user = self.store.find_user(kind, value)

        invalid = AuthError(401, "invalid_credentials", "Wrong account or password.")

        if user is None:
            security.verify_password(password, _DUMMY_HASH)       # same time as a real check
            raise invalid

        if user["locked_until"] > now:
            wait = user["locked_until"] - now
            raise AuthError(429, "account_locked", "Too many failed attempts. Try again later.", wait)

        if not security.verify_password(password, user["password_hash"]):

            failed = user["failed_logins"] + 1
            fields = {"failed_logins": failed}

            if failed >= s.AUTH_MAX_FAILED_LOGINS:
                fields.update(failed_logins=0, locked_until=now + s.AUTH_LOCK_MINUTES * 60)

            self.store.update_user(user["id"], **fields)

            raise invalid

        if not self._verified(user, kind):
            raise AuthError(403, "not_verified", "Verify your account first (a code was sent at sign-up).")

        if not user["is_active"]:
            raise AuthError(403, "account_disabled", "This account is disabled.")

        fields = {"failed_logins": 0, "locked_until": 0, "last_login_at": now}

        if security.needs_rehash(user["password_hash"]):
            fields["password_hash"] = security.hash_password(password)

        self.store.update_user(user["id"], **fields)

        return self._issue_tokens(self.store.get_user(user["id"]))

    def request_login_code(self, identifier: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        user = self.store.find_user(kind, value)

        usable = user is not None and self._verified(user, kind) and bool(user["is_active"])

        self._send_code(kind, value, "login", deliver=usable)

        return {"message": GENERIC_CODE_SENT}

    def login_with_code(self, identifier: str, code: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        self._check_code(value, "login", code)

        user = self.store.find_user(kind, value)

        if user is None or not self._verified(user, kind) or not user["is_active"]:
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

        self.store.update_user(user["id"], last_login_at=self._now(), failed_logins=0)

        return self._issue_tokens(self.store.get_user(user["id"]))

    # ------------------------------------------------------------------
    # refresh / logout
    # ------------------------------------------------------------------

    def refresh(self, refresh_token: str) -> Dict[str, Any]:

        invalid = AuthError(401, "invalid_token", "Invalid refresh token.")

        row = self.store.find_refresh(security.hash_token(refresh_token or ""))

        if row is None or row["revoked"]:
            raise invalid

        if row["used"]:
            # an already-used token came back: it was stolen or replayed.
            # Close the whole session family.
            self.store.revoke_family(row["family_id"])
            raise AuthError(401, "token_reuse_detected", "This session is no longer valid. Sign in again.")

        if row["expires_at"] <= self._now():
            raise invalid

        user = self.store.get_user(row["user_id"])

        if user is None or not user["is_active"]:
            raise invalid

        if not self.store.mark_refresh_used(row["id"]):
            self.store.revoke_family(row["family_id"])
            raise AuthError(401, "token_reuse_detected", "This session is no longer valid. Sign in again.")

        return self._issue_tokens(user, family_id=row["family_id"])

    def logout(self, refresh_token: str) -> Dict[str, Any]:

        row = self.store.find_refresh(security.hash_token(refresh_token or ""))

        if row is not None:
            self.store.revoke_family(row["family_id"])

        return {"message": "Signed out."}

    def logout_all(self, user_id: str) -> Dict[str, Any]:

        self.store.bump_token_version(user_id)
        self.store.revoke_user_tokens(user_id)

        return {"message": "Signed out everywhere."}

    # ------------------------------------------------------------------
    # passwords
    # ------------------------------------------------------------------

    def forgot_password(self, identifier: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        user = self.store.find_user(kind, value)

        self._send_code(kind, value, "reset", deliver=user is not None and bool(user["is_active"]))

        return {"message": GENERIC_CODE_SENT}

    def reset_password(self, identifier: str, code: str, new_password: str) -> Dict[str, Any]:

        kind, value = self.normalize_identifier(identifier)

        self._check_password(new_password, value)
        self._check_code(value, "reset", code)

        user = self.store.find_user(kind, value)

        if user is None:
            raise AuthError(400, "invalid_code", "The code is wrong or expired.")

        self.store.update_user(
            user["id"],
            password_hash=security.hash_password(new_password),
            failed_logins=0, locked_until=0,
            **{f"{kind}_verified": True},        # the code proved the owner
        )

        # every open session of this account ends now
        self.store.bump_token_version(user["id"])
        self.store.revoke_user_tokens(user["id"])

        return {"message": "Password updated. Sign in with the new password."}

    def change_password(self, user_id: str, current_password: str, new_password: str) -> Dict[str, Any]:

        user = self.store.get_user(user_id)

        if user is None or not security.verify_password(current_password, user["password_hash"]):
            raise AuthError(400, "wrong_password", "The current password is wrong.")

        self._check_password(new_password, user["email"] or user["phone"] or "")

        self.store.update_user(user_id, password_hash=security.hash_password(new_password))
        self.store.bump_token_version(user_id)
        self.store.revoke_user_tokens(user_id)

        return self._issue_tokens(self.store.get_user(user_id))

    # ------------------------------------------------------------------
    # administration
    # ------------------------------------------------------------------

    def list_users(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:

        return [self.public_user(u) for u in self.store.list_users(min(limit, 200), max(offset, 0))]

    def update_user(self, admin_id: str, user_id: str, role: Optional[str], is_active: Optional[bool]) -> Dict[str, Any]:

        if user_id == admin_id:
            raise AuthError(400, "cannot_change_self", "You cannot change your own role or status.")

        user = self.store.get_user(user_id)

        if user is None:
            raise AuthError(404, "not_found", "User not found.")

        fields: Dict[str, Any] = {}

        if role is not None:
            fields["role"] = role

        if is_active is not None:
            fields["is_active"] = is_active

        if fields:
            self.store.update_user(user_id, **fields)
            # take effect immediately: old tokens of this user stop working
            self.store.bump_token_version(user_id)

            if is_active is False:
                self.store.revoke_user_tokens(user_id)

        return self.public_user(self.store.get_user(user_id))
