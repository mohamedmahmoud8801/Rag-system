import os
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from ..SQLInterface import SQLInterface, Statement


class SQLiteProvider(SQLInterface):

    # Read-only queries are interrupted after this many seconds.
    QUERY_TIMEOUT_SECONDS = 15

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Optional[Engine] = None
        self._deadline: Optional[float] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:

        if self.engine is not None:
            return

        engine = create_engine(
            self.database_url,
            future=True,
            pool_pre_ping=True,
        )

        # pysqlite normally decides by itself when to BEGIN and does not
        # make DDL transactional. Taking control gives us real atomic
        # transactions (CREATE TABLE + INSERT roll back together).
        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection, _record):
            dbapi_connection.isolation_level = None
            dbapi_connection.set_progress_handler(
                self._progress_handler,
                20000,
            )

        @event.listens_for(engine, "begin")
        def _on_begin(connection):
            connection.exec_driver_sql("BEGIN")

        self.engine = engine

    def disconnect(self) -> None:

        if self.engine is not None:
            self.engine.dispose()
            self.engine = None

    def _progress_handler(self) -> int:
        # Returning non-zero makes SQLite abort the running statement.
        if self._deadline is not None and time.monotonic() > self._deadline:
            return 1
        return 0

    def _ensure_directory(self) -> None:

        database = self.engine.url.database

        if (
            database
            and database != ":memory:"
            and not str(database).startswith("file:")
        ):
            os.makedirs(
                os.path.dirname(os.path.abspath(database)),
                exist_ok=True,
            )

    def validate_connection(self) -> bool:

        try:
            self.connect()

            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return True

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_tables(self) -> List[str]:

        self.connect()

        return inspect(self.engine).get_table_names()

    def get_schema(
        self,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:

        self.connect()

        inspector = inspect(self.engine)

        available_tables = inspector.get_table_names()

        if tables is None:
            tables = available_tables
        else:
            tables = [t for t in tables if t in available_tables]

        schema = {}

        for table_name in tables:

            columns = inspector.get_columns(table_name)

            primary_key_columns = inspector.get_pk_constraint(
                table_name
            ).get("constrained_columns", [])

            foreign_keys = inspector.get_foreign_keys(table_name)

            schema[table_name] = {

                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column.get("nullable", True),
                        "primary_key": column["name"] in primary_key_columns,
                    }
                    for column in columns
                ],

                "foreign_keys": [
                    {
                        "column": column_name,
                        "references_table": fk.get("referred_table"),
                        "references_column": referred_column,
                    }
                    for fk in foreign_keys
                    for column_name, referred_column in zip(
                        fk.get("constrained_columns", []),
                        fk.get("referred_columns", []),
                    )
                ],
            }

        return schema

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _to_text(query: str, params: Optional[Dict[str, Any]]):
        # Without bind parameters, a ':' inside a string literal must not
        # be read as a bind marker (e.g. WHERE note = ':abc').
        if params:
            return text(query)
        return text(query.replace(":", "\\:"))

    @staticmethod
    def _collect(result, max_rows: Optional[int]) -> Dict[str, Any]:

        columns = list(result.keys())
        mappings = result.mappings()

        if max_rows is None:
            rows = [dict(row) for row in mappings.all()]
            truncated = False
        else:
            fetched = mappings.fetchmany(max_rows + 1)
            truncated = len(fetched) > max_rows
            rows = [dict(row) for row in fetched[:max_rows]]

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        max_rows: Optional[int] = None,
        read_only: bool = False,
    ) -> Dict[str, Any]:

        self.connect()

        with self.engine.begin() as connection:

            if read_only:
                connection.exec_driver_sql("PRAGMA query_only = ON")
                self._deadline = (
                    time.monotonic() + self.QUERY_TIMEOUT_SECONDS
                )

            try:
                result = connection.execute(
                    self._to_text(query, params),
                    params or {},
                )

                # CREATE / INSERT / UPDATE / DELETE return no rows.
                if not result.returns_rows:
                    return {
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "truncated": False,
                    }

                return self._collect(result, max_rows)

            finally:
                self._deadline = None

                if read_only:
                    try:
                        connection.exec_driver_sql("PRAGMA query_only = OFF")
                    except Exception:
                        pass

    def execute_transaction(self, statements: List[Statement]) -> None:

        self.connect()
        self._ensure_directory()

        with self.engine.begin() as connection:

            for sql, rows in statements:

                if rows:
                    connection.execute(text(sql), rows)
                else:
                    connection.exec_driver_sql(sql)