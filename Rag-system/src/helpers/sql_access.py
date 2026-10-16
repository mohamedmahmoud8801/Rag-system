import re
from pathlib import Path
from typing import Optional, Tuple

from helpers.config import get_settings


class SQLTargetNotAllowed(ValueError):
    """The client asked for a database the server does not allow."""


# ----------------------------------------------------------------------
# Two SEPARATE data sources
#
#   1. Excel store      "excel://<project_id>"
#      Excel sheets become tables in a SQLite file that belongs to that
#      project (EXCEL_SQL_DIR/project_<id>.db). Nothing else lives there.
#
#   2. Connected database   (no URL, or the configured SQL_DATABASE_URL)
#      The database the user connects. The Excel feature never writes
#      into it.
# ----------------------------------------------------------------------

EXCEL_SCHEME = "excel://"

#   3. Saved connection   "conn://<connection_id>"
#      A database the user connected from the Connect database screen
#      (PostgreSQL or a SQLite file). The URL, with its password, is stored
#      encrypted and never leaves the server.
CONNECTION_SCHEME = "conn://"

# URLs this process resolved from a saved connection a moment ago. Internal
# calls pass the resolved URL on, so it must be accepted again. A client
# cannot use this: it would need to know the full URL, password included.
_TRUSTED_RESOLVED: dict = {}


def _remember(url: str, provider: str) -> None:

    if len(_TRUSTED_RESOLVED) > 256:
        _TRUSTED_RESOLVED.clear()

    _TRUSTED_RESOLVED[url] = provider


def _project_number(project_id) -> int:

    if not re.fullmatch(r"\d+", str(project_id).strip()):
        raise SQLTargetNotAllowed(
            f"Invalid project id for an Excel store: {project_id!r}."
        )

    return int(str(project_id).strip())


def excel_store_url(project_id) -> str:

    directory = get_settings().EXCEL_SQL_DIR.strip("/\\") or "assets/database/excel"

    return f"sqlite:///{directory}/project_{_project_number(project_id)}.db"


def _excel_directory() -> str:

    return get_settings().EXCEL_SQL_DIR.strip("/\\") or "assets/database/excel"


def excel_store_path(project_id) -> Path:

    return Path(_excel_directory()) / f"project_{_project_number(project_id)}.db"


def ensure_excel_store_dir() -> None:
    """The folder of the Excel stores is created the first time it is needed."""

    Path(_excel_directory()).mkdir(parents=True, exist_ok=True)


def excel_database_url(project_id) -> str:
    """The value a client sends as database_url to query an Excel store."""

    return f"{EXCEL_SCHEME}{_project_number(project_id)}"


def _is_excel_store_url(database_url: str) -> bool:

    directory = re.escape(
        get_settings().EXCEL_SQL_DIR.strip("/\\") or "assets/database/excel"
    )

    return bool(
        re.fullmatch(rf"sqlite:///{directory}/project_\d+\.db", database_url)
    )


def _infer_provider(database_url: str) -> str:

    scheme = database_url.split(":", 1)[0].lower()

    if scheme.startswith("sqlite"):
        return "sqlite"

    if scheme.startswith("postgres"):
        return "postgresql"

    raise SQLTargetNotAllowed(
        f"Cannot infer the SQL provider from database_url scheme '{scheme}'."
    )


def resolve_sql_target(
    provider: Optional[str],
    database_url: Optional[str],
) -> Tuple[str, str]:
    """
    Decide which database a request may use.

    - "excel://<project_id>"  -> that project's Excel store (always allowed;
                                 it is internal and only holds Excel data).
    - no database_url (or the configured one) -> the connected database
                                 from SQL_PROVIDER / SQL_DATABASE_URL.
    - any other database_url  -> only if SQL_ALLOW_CLIENT_DATABASE_URL=true.
    """

    settings = get_settings()

    # ---- 3. Saved connection ----
    if database_url and database_url.startswith(CONNECTION_SCHEME):

        from stores.sql import ConnectionSecurity
        from stores.sql.ConnectionStore import ConnectionStore

        record = ConnectionStore().get(database_url[len(CONNECTION_SCHEME):])

        if provider and provider.lower() != record["provider"]:
            raise SQLTargetNotAllowed(
                f"provider '{provider}' does not match this connection "
                f"('{record['provider']}'). Omit provider."
            )

        # re-checked on every use (DNS can change, files can be replaced)
        ConnectionSecurity.assert_record_allowed(record)

        _remember(record["url"], record["provider"])

        return record["provider"], record["url"]

    if database_url and database_url in _TRUSTED_RESOLVED:
        return _TRUSTED_RESOLVED[database_url], database_url

    # ---- 1. Excel store ----
    if database_url and (
        database_url.startswith(EXCEL_SCHEME)
        or _is_excel_store_url(database_url)
    ):

        if provider and provider.lower() != "sqlite":
            raise SQLTargetNotAllowed(
                "An Excel store is a SQLite file; provider must be 'sqlite'."
            )

        if database_url.startswith(EXCEL_SCHEME):
            project_id = database_url[len(EXCEL_SCHEME):]
            resolved = excel_store_url(project_id)
        else:
            project_id = None
            resolved = database_url

        # Asking about a project that has no Excel data yet must not create
        # an empty database file: say what to do instead.
        if project_id is not None and not excel_store_path(project_id).exists():
            raise SQLTargetNotAllowed(
                f"No Excel data has been loaded for project {project_id} yet. "
                "Load a file first: POST /sql/ingest."
            )

        return "sqlite", resolved

    # ---- 2. Connected database ----
    configured_url = settings.SQL_DATABASE_URL
    configured_provider = (settings.SQL_PROVIDER or "sqlite").lower()

    if not database_url or database_url == configured_url:

        if provider and provider.lower() != configured_provider:
            raise SQLTargetNotAllowed(
                f"provider '{provider}' does not match the configured "
                f"SQL provider '{configured_provider}'. "
                "Omit provider and database_url to use the server database."
            )

        return configured_provider, configured_url

    if not settings.SQL_ALLOW_CLIENT_DATABASE_URL:
        raise SQLTargetNotAllowed(
            "Custom database_url is disabled on this server. "
            "Omit database_url to use the configured database, or set "
            "SQL_ALLOW_CLIENT_DATABASE_URL=true."
        )

    return (provider or _infer_provider(database_url)).lower(), database_url