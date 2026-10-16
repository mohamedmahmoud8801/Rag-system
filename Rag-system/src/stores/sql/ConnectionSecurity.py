import ipaddress
import os
import re
import socket
import time
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

from sqlalchemy.engine import URL

from helpers.config import get_settings


class ConnectionNotAllowed(ValueError):
    """The requested connection is refused by the server's safety rules."""


SQLITE_MAGIC = b"SQLite format 3\x00"

_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]{0,251}[A-Za-z0-9])?$")

_BLOCKED_HINT = (
    "Connections to localhost, private or reserved addresses are blocked on "
    "this server. On a trusted machine set CONNECTIONS_ALLOW_PRIVATE_HOSTS=true."
)

# host -> (checked_at) so one query does not trigger many DNS lookups
_HOST_OK_CACHE: dict = {}
_HOST_OK_TTL = 60


# ----------------------------------------------------------------------
# PostgreSQL
# ----------------------------------------------------------------------

def _ip_is_blocked(ip) -> bool:

    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def check_host(host: str) -> None:
    """
    Refuses hosts that resolve to loopback / private / link-local ranges
    (stops the server from being used to reach internal services or cloud
    metadata endpoints). Checked on the RESOLVED addresses, so decimal or
    hex IP tricks do not work either.
    """

    host = (host or "").strip()

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is None and not _HOST_RE.match(host):
        raise ConnectionNotAllowed("Invalid host name.")

    if get_settings().CONNECTIONS_ALLOW_PRIVATE_HOSTS:
        return

    cached = _HOST_OK_CACHE.get(host)

    if cached and time.monotonic() - cached < _HOST_OK_TTL:
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ConnectionNotAllowed(f"Cannot resolve host: {host}")

    for info in infos:

        address = info[4][0].split("%")[0]

        if _ip_is_blocked(ipaddress.ip_address(address)):
            raise ConnectionNotAllowed(_BLOCKED_HINT)

    _HOST_OK_CACHE[host] = time.monotonic()


def postgres_url(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    ssl: bool = False,
) -> str:

    if not (1 <= int(port) <= 65535):
        raise ConnectionNotAllowed("Port must be between 1 and 65535.")

    if not database or not username:
        raise ConnectionNotAllowed("database and username are required.")

    check_host(host)

    url = URL.create(
        "postgresql+psycopg2",
        username=username,
        password=password or None,
        host=host,
        port=int(port),
        database=database,
        query={
            "connect_timeout": "10",
            "sslmode": "require" if ssl else "prefer",
        },
    )

    return url.render_as_string(hide_password=False)


# ----------------------------------------------------------------------
# SQLite (only files inside SQLITE_CONNECT_DIR)
# ----------------------------------------------------------------------

def sqlite_directory() -> Path:

    return Path(get_settings().SQLITE_CONNECT_DIR).resolve()


def has_sqlite_header(path: Path) -> bool:

    with open(path, "rb") as handle:
        return handle.read(16) == SQLITE_MAGIC


def resolve_sqlite_file(name: str) -> Path:
    """File NAME only. Never a path, never outside SQLITE_CONNECT_DIR."""

    if (
        not name
        or name != os.path.basename(name)
        or "\\" in name
        or "\x00" in name
        or name.startswith(".")
    ):
        raise ConnectionNotAllowed(
            "Give only the name of a SQLite file from the allowed folder."
        )

    directory = sqlite_directory()
    path = (directory / name).resolve()

    # blocks symlinks pointing outside the folder
    if path.parent != directory:
        raise ConnectionNotAllowed("SQLite file must be inside the allowed folder.")

    if not path.is_file():
        raise ConnectionNotAllowed(f"SQLite file not found: {name}")

    if not has_sqlite_header(path):
        raise ConnectionNotAllowed(f"{name} is not a SQLite database.")

    return path


def sqlite_readonly_url(path: Path) -> str:
    """The database itself refuses writes (mode=ro)."""

    return f"sqlite:///file:{quote(str(path))}?mode=ro&uri=true"


# ----------------------------------------------------------------------
# Re-check a SAVED connection every time it is used
# ----------------------------------------------------------------------

def assert_record_allowed(record: dict) -> None:

    meta = record.get("meta") or {}

    if record["provider"] == "postgresql":
        check_host(meta.get("host", ""))

    elif record["provider"] == "sqlite":
        resolve_sqlite_file(meta.get("file", ""))


# ----------------------------------------------------------------------
# Errors that never contain the password
# ----------------------------------------------------------------------

def safe_error(error: BaseException, secrets: Iterable[Optional[str]] = ()) -> str:

    message = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__

    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")

    message = re.sub(r"(://[^:/\s]+):[^@\s]+@", r"\1:***@", message)

    return message[:300]