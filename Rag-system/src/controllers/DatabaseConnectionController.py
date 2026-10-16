import asyncio
import os
import re
import uuid
from typing import Any, Dict, Optional

from helpers.config import get_settings
from stores.sql import ConnectionSecurity as security
from stores.sql.ConnectionSecurity import ConnectionNotAllowed
from stores.sql.ConnectionStore import ConnectionStore
from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLProviderFactory import SQLProviderFactory


class ConnectionTestFailed(ValueError):
    """The database did not accept the connection (message is password-free)."""


_DRIVER_HINT = (
    "The PostgreSQL driver is not installed on the server "
    "(pip install psycopg2-binary)."
)


class DatabaseConnectionController:
    """Test, save, list and delete the databases a user connects."""

    PROBE_TIMEOUT_SECONDS = 25
    MAX_TABLES_LISTED = 100

    def __init__(self, store: Optional[ConnectionStore] = None):
        self.store = store or ConnectionStore()

    # ------------------------------------------------------------------
    # Validate the form -> (provider, url, display, meta, secrets)
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare(params: Dict[str, Any]):

        provider = (params.get("provider") or "").strip().lower()

        if provider == "postgres":
            provider = "postgresql"

        if provider == "postgresql":

            host = (params.get("host") or "").strip()
            database = (params.get("database") or "").strip()
            username = (params.get("username") or "").strip()
            password = params.get("password") or ""
            port = int(params.get("port") or 5432)
            ssl = bool(params.get("ssl"))

            if not host:
                raise ConnectionNotAllowed("host is required.")

            url = security.postgres_url(
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                ssl=ssl,
            )

            return (
                provider,
                url,
                f"postgresql://{username}@{host}:{port}/{database}",
                {"host": host, "port": port, "database": database,
                 "username": username, "ssl": ssl},
                [password],
            )

        if provider == "sqlite":

            path = security.resolve_sqlite_file((params.get("file") or "").strip())

            return (
                provider,
                security.sqlite_readonly_url(path),
                f"sqlite:{path.name}",
                {"file": path.name},
                [],
            )

        raise ConnectionNotAllowed("provider must be 'postgresql' or 'sqlite'.")

    # ------------------------------------------------------------------
    # Really connect (blocking, so it runs in a thread with a timeout)
    # ------------------------------------------------------------------

    @staticmethod
    def _probe(provider: str, url: str, secrets) -> Dict[str, Any]:

        sql_provider = SQLProviderFactory.create(
            provider=SQLProviderEnum(provider),
            database_url=url,
        )

        try:
            sql_provider.connect()

            # opens a real connection AND proves the read-only mode works
            sql_provider.execute("SELECT 1", read_only=True)

            tables = sorted(sql_provider.get_tables())

        except ModuleNotFoundError:
            raise ConnectionTestFailed(_DRIVER_HINT)

        except Exception as exc:
            raise ConnectionTestFailed(security.safe_error(exc, secrets))

        finally:
            sql_provider.disconnect()

        return {
            "table_count": len(tables),
            "tables": tables[:DatabaseConnectionController.MAX_TABLES_LISTED],
        }

    async def _probe_async(self, provider, url, secrets) -> Dict[str, Any]:

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._probe, provider, url, secrets),
                timeout=self.PROBE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise ConnectionTestFailed("The database did not answer in time.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def test(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Never raises: the form shows the message."""

        try:
            provider, url, display, _meta, secrets = self._prepare(params)
            probe = await self._probe_async(provider, url, secrets)

        except (ConnectionNotAllowed, ConnectionTestFailed) as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "provider": provider, "display": display, **probe}

    async def create(
        self,
        project_id: int,
        name: str,
        params: Dict[str, Any],
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        name = (name or "").strip()

        if not 1 <= len(name) <= 80:
            raise ConnectionNotAllowed("name must be 1 to 80 characters.")

        if self.store.count(project_id) >= get_settings().CONNECTIONS_MAX_PER_PROJECT:
            raise ConnectionNotAllowed(
                "This project reached the maximum number of connections."
            )

        provider, url, display, meta, secrets = self._prepare(params)

        probe = await self._probe_async(provider, url, secrets)

        record = self.store.create(
            project_id=project_id,
            name=name,
            provider=provider,
            url=url,
            display=display,
            meta={**meta, **(extra_meta or {})},
        )

        return {**record, **probe}

    async def create_from_sqlite_upload(self, project_id: int, name: str, upload) -> Dict[str, Any]:
        """A SQLite file uploaded from the browser (opened read-only)."""

        limit = get_settings().SQLITE_UPLOAD_MAX_MB * 1048576

        data = await upload.read(limit + 1)

        if len(data) > limit:
            raise ConnectionNotAllowed(
                f"The file is larger than {get_settings().SQLITE_UPLOAD_MAX_MB} MB."
            )

        if data[:16] != security.SQLITE_MAGIC:
            raise ConnectionNotAllowed("The uploaded file is not a SQLite database.")

        original = os.path.basename(upload.filename or "database.db")
        cleaned = re.sub(r"[^\w.\- ]+", "_", original).lstrip(".") or "database.db"
        saved_name = f"{uuid.uuid4().hex[:10]}_{cleaned}"

        directory = security.sqlite_directory()
        directory.mkdir(parents=True, exist_ok=True)

        saved_path = directory / saved_name
        saved_path.write_bytes(data)

        try:
            return await self.create(
                project_id,
                name,
                {"provider": "sqlite", "file": saved_name},
                extra_meta={"uploaded": True},
            )
        except Exception:
            saved_path.unlink(missing_ok=True)
            raise

    def list(self, project_id: int):
        return self.store.list(project_id)

    def delete(self, project_id: int, connection_id: str) -> bool:

        meta = self.store.delete(project_id, connection_id)

        if meta is None:
            return False

        # a file the user uploaded goes away with its connection
        if meta.get("uploaded") and meta.get("file"):
            (security.sqlite_directory() / meta["file"]).unlink(missing_ok=True)

        return True