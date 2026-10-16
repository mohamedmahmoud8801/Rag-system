import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from helpers.config import get_settings
from stores.sql.ConnectionSecurity import ConnectionNotAllowed


class ConnectionStore:
    """
    Saved database connections. The connection URL (it contains the
    password) is stored ENCRYPTED with Fernet; the API only ever returns a
    masked description and the connection_id.
    """

    def __init__(self, path: Optional[str] = None):

        settings = get_settings()

        self.path = Path(path or settings.CONNECTIONS_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._fernet = self._load_fernet()
        self._create_table()

    # ------------------------------------------------------------------

    def _load_fernet(self) -> Fernet:

        key = get_settings().CONNECTIONS_SECRET_KEY

        if not key:

            key_file = self.path.parent / ".connections.key"

            if key_file.exists():
                key = key_file.read_text().strip()
            else:
                key = Fernet.generate_key().decode()
                key_file.write_text(key)
                try:
                    os.chmod(key_file, 0o600)
                except OSError:
                    pass

        try:
            return Fernet(key.encode())
        except Exception:
            raise ConnectionNotAllowed(
                "CONNECTIONS_SECRET_KEY is not a valid Fernet key."
            )

    def _connect(self) -> sqlite3.Connection:

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row

        return connection

    def _create_table(self) -> None:

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS db_connections (
                    id TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    url_encrypted TEXT NOT NULL,
                    display TEXT NOT NULL,
                    meta TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------

    @staticmethod
    def _public(row: sqlite3.Row) -> Dict[str, Any]:

        return {
            "connection_id": row["id"],
            "project_id": row["project_id"],
            "name": row["name"],
            "provider": row["provider"],
            "display": row["display"],
            "database_url": f"conn://{row['id']}",
            "created_at": row["created_at"],
        }

    def count(self, project_id: int) -> int:

        with self._connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM db_connections WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

    def create(
        self,
        project_id: int,
        name: str,
        provider: str,
        url: str,
        display: str,
        meta: Dict[str, Any],
    ) -> Dict[str, Any]:

        connection_id = uuid.uuid4().hex

        with self._connect() as connection:
            connection.execute(
                "INSERT INTO db_connections VALUES (?,?,?,?,?,?,?,?)",
                (
                    connection_id,
                    project_id,
                    name,
                    provider,
                    self._fernet.encrypt(url.encode()).decode(),
                    display,
                    json.dumps(meta),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )

            row = connection.execute(
                "SELECT * FROM db_connections WHERE id = ?", (connection_id,)
            ).fetchone()

        return self._public(row)

    def list(self, project_id: int) -> List[Dict[str, Any]]:

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM db_connections WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()

        return [self._public(row) for row in rows]

    def get(self, connection_id: str) -> Dict[str, Any]:
        """Server-side only: includes the decrypted URL."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM db_connections WHERE id = ?", (connection_id,)
            ).fetchone()

        if row is None:
            raise ConnectionNotAllowed("Unknown database connection.")

        try:
            url = self._fernet.decrypt(row["url_encrypted"].encode()).decode()
        except InvalidToken:
            raise ConnectionNotAllowed(
                "The saved connection cannot be decrypted (the secret key "
                "changed). Create it again."
            )

        return {
            **self._public(row),
            "url": url,
            "meta": json.loads(row["meta"]),
        }

    def delete(self, project_id: int, connection_id: str) -> Optional[Dict[str, Any]]:
        """Returns the deleted connection's meta, or None if it did not exist."""

        with self._connect() as connection:

            row = connection.execute(
                "SELECT meta FROM db_connections WHERE id = ? AND project_id = ?",
                (connection_id, project_id),
            ).fetchone()

            if row is None:
                return None

            connection.execute(
                "DELETE FROM db_connections WHERE id = ? AND project_id = ?",
                (connection_id, project_id),
            )

        return json.loads(row["meta"])