import math
import re
import unicodedata
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple

from controllers.ProcessController import ProcessController
from helpers.config import get_settings
from helpers.sql_access import (
    ensure_excel_store_dir,
    excel_database_url,
    excel_store_url,
)
from stores.sql.SchemaCache import schema_cache
from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLProviderFactory import SQLProviderFactory


class ExcelSQLController:
    """
    Loads every sheet of an uploaded Excel file into its own SQL table.

    - Arabic (and any Unicode) headers keep their real names.
    - Every identifier is quoted, so names such as "order" or "group" work.
    - Tables and columns get unique names (sheet-1 / Sheet 1, duplicate
      headers, ...).
    - Dates become DATE / TIMESTAMP columns.
    - All tables of a file are created in ONE transaction: either the whole
      file is ingested or nothing changes.
    """

    # PostgreSQL limits identifiers to 63 *bytes* (Arabic = 2 bytes/char).
    MAX_IDENTIFIER_BYTES = 60
    INSERT_CHUNK_SIZE = 2000
    INT64_MAX = 2 ** 63 - 1

    def __init__(
        self,
        project_id: str,
        provider: Optional[str] = None,
        database_url: Optional[str] = None,
    ):
        # Excel data goes to the project's OWN Excel store, never into a
        # database the user connected. provider/database_url are only kept
        # so old clients get a clear error instead of a silent change.
        if provider or database_url:
            raise ValueError(
                "Excel ingest does not accept provider or database_url: the "
                "sheets are stored in the project's own Excel database. Query "
                f"them with database_url='excel://{project_id}'."
            )

        self.project_id = project_id
        self.provider = SQLProviderEnum.SQLITE
        self.database_url = excel_store_url(project_id)

        self.process_controller = ProcessController(
            project_id=project_id
        )

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------

    @classmethod
    def _truncate(cls, name: str) -> str:

        while len(name.encode("utf-8")) > cls.MAX_IDENTIFIER_BYTES:
            name = name[:-1]

        return name

    @classmethod
    def _sanitize_identifier(cls, value: Any, fallback: str) -> str:

        original = str(value).strip()

        if original == "#":
            return "column_number"

        text = unicodedata.normalize("NFKC", original).lower()

        # \w keeps letters/digits of every script (Arabic included).
        text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
        text = re.sub(r"_+", "_", text).strip("_")

        if not text:
            text = fallback

        if text[0].isdigit():
            text = f"column_{text}"

        return cls._truncate(text)

    @classmethod
    def _unique_name(cls, name: str, used: set) -> str:

        base = cls._truncate(name)
        candidate = base
        counter = 2

        while candidate.lower() in used:

            suffix = f"_{counter}"
            trimmed = base

            while len((trimmed + suffix).encode("utf-8")) > cls.MAX_IDENTIFIER_BYTES:
                trimmed = trimmed[:-1]

            candidate = trimmed + suffix
            counter += 1

        used.add(candidate.lower())

        return candidate

    @staticmethod
    def _quote(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    # ------------------------------------------------------------------
    # Types and values
    # ------------------------------------------------------------------

    def _infer_type(self, values: List[Any]) -> str:

        non_null = [value for value in values if value is not None]

        if not non_null:
            return "TEXT"

        kinds = set()

        for value in non_null:
            if isinstance(value, bool):
                kinds.add("bool")
            elif isinstance(value, int):
                kinds.add("int")
            elif isinstance(value, float):
                kinds.add("float")
            elif isinstance(value, datetime):
                kinds.add("datetime")
            elif isinstance(value, date):
                kinds.add("date")
            else:
                kinds.add("text")

        if kinds == {"bool"}:
            return "BOOLEAN"

        if kinds == {"int"}:
            if any(abs(value) > self.INT64_MAX for value in non_null):
                return "TEXT"
            return (
                "BIGINT"
                if self.provider == SQLProviderEnum.POSTGRESQL
                else "INTEGER"
            )

        if kinds <= {"int", "float"}:
            return "FLOAT"

        if kinds == {"date"}:
            return "DATE"

        if kinds <= {"date", "datetime"}:
            midnight_only = all(
                value.time() == time(0, 0)
                for value in non_null
                if isinstance(value, datetime)
            )
            return "DATE" if midnight_only else "TIMESTAMP"

        return "TEXT"

    def _coerce(self, value: Any, sql_type: str) -> Any:

        if value is None:
            return None

        is_sqlite = self.provider == SQLProviderEnum.SQLITE

        if sql_type == "TEXT":
            if isinstance(value, datetime):
                return value.isoformat(sep=" ")
            if isinstance(value, date):
                return value.isoformat()
            return str(value)

        if sql_type == "FLOAT":
            number = float(value)
            return number if math.isfinite(number) else None

        if sql_type in ("INTEGER", "BIGINT"):
            return int(value)

        if sql_type == "BOOLEAN":
            return bool(value)

        if sql_type == "DATE":
            day = value.date() if isinstance(value, datetime) else value
            return day.isoformat() if is_sqlite else day

        if sql_type == "TIMESTAMP":
            if not isinstance(value, datetime):
                value = datetime(value.year, value.month, value.day)
            return value.isoformat(sep=" ") if is_sqlite else value

        return value

    # ------------------------------------------------------------------
    # Table definitions
    # ------------------------------------------------------------------

    def _load_sheets(self, file_id: str) -> List[Dict[str, Any]]:

        sheets = self.process_controller.get_excel_structured_content(
            file_id=file_id
        )

        if sheets is None:
            raise ValueError("Failed to extract Excel data")

        return sheets

    def _build_definitions(
        self,
        sheets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        max_rows = get_settings().EXCEL_MAX_ROWS_PER_SHEET

        used_tables: set = set()
        definitions = []

        for sheet in sheets:

            columns = sheet["columns"]
            records = sheet["records"]

            if not columns:
                continue

            if len(records) > max_rows:
                raise ValueError(
                    f"Sheet '{sheet['sheet_name']}' has {len(records)} rows "
                    f"(limit: {max_rows})."
                )

            table_name = self._unique_name(
                self._sanitize_identifier(
                    sheet["sheet_name"],
                    fallback="excel_table",
                ),
                used_tables,
            )

            used_columns: set = set()
            column_definitions = []

            for index, column in enumerate(columns):

                name = self._unique_name(
                    self._sanitize_identifier(
                        column,
                        fallback=f"column_{index + 1}",
                    ),
                    used_columns,
                )

                column_definitions.append(
                    {
                        "original_name": column,
                        "name": name,
                        "type": self._infer_type(
                            [record.get(column) for record in records]
                        ),
                    }
                )

            definitions.append(
                {
                    "sheet_name": sheet["sheet_name"],
                    "table_name": table_name,
                    "columns": column_definitions,
                    "row_count": len(records),
                }
            )

        return definitions

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _create_sql(self, definition: Dict[str, Any]) -> str:

        columns = ", ".join(
            f"{self._quote(column['name'])} {column['type']}"
            for column in definition["columns"]
        )

        return (
            f"CREATE TABLE {self._quote(definition['table_name'])} "
            f"({columns})"
        )

    def _insert_payload(
        self,
        definition: Dict[str, Any],
        records: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]]]:

        columns = definition["columns"]

        insert_sql = (
            f"INSERT INTO {self._quote(definition['table_name'])} ("
            + ", ".join(self._quote(c["name"]) for c in columns)
            + ") VALUES ("
            + ", ".join(f":c{index}" for index in range(len(columns)))
            + ")"
        )

        rows = [
            {
                f"c{index}": self._coerce(
                    record.get(column["original_name"]),
                    column["type"],
                )
                for index, column in enumerate(columns)
            }
            for record in records
        ]

        return insert_sql, rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def preview(self, file_id: str) -> List[Dict[str, Any]]:

        return self._build_definitions(self._load_sheets(file_id))

    async def ingest(
        self,
        file_id: str,
        if_exists: str = "fail",
    ) -> Dict[str, Any]:
        """
        if_exists = "fail"    -> refuse if a table with that name exists
        if_exists = "replace" -> drop and recreate tables with the same name
        """

        if if_exists not in ("fail", "replace"):
            raise ValueError("if_exists must be 'fail' or 'replace'.")

        sheets = self._load_sheets(file_id)
        definitions = self._build_definitions(sheets)

        if not definitions:
            raise ValueError("No Excel table definitions found")

        # first run: the folder of the Excel stores may not exist yet
        ensure_excel_store_dir()

        records_by_sheet = {
            sheet["sheet_name"]: sheet["records"] for sheet in sheets
        }

        provider = SQLProviderFactory.create(
            provider=self.provider,
            database_url=self.database_url,
        )

        try:

            existing = {name.lower() for name in provider.get_tables()}

            conflicts = [
                d["table_name"]
                for d in definitions
                if d["table_name"].lower() in existing
            ]

            if conflicts and if_exists == "fail":
                raise ValueError(
                    f"Tables already exist: {', '.join(conflicts)}. "
                    "Use if_exists='replace' to overwrite them."
                )

            statements = []
            summary = []

            for definition in definitions:

                replaced = definition["table_name"].lower() in existing

                if replaced:
                    statements.append(
                        (
                            f"DROP TABLE IF EXISTS "
                            f"{self._quote(definition['table_name'])}",
                            None,
                        )
                    )

                statements.append((self._create_sql(definition), None))

                insert_sql, rows = self._insert_payload(
                    definition,
                    records_by_sheet[definition["sheet_name"]],
                )

                for start in range(0, len(rows), self.INSERT_CHUNK_SIZE):
                    statements.append(
                        (
                            insert_sql,
                            rows[start:start + self.INSERT_CHUNK_SIZE],
                        )
                    )

                summary.append(
                    {
                        "sheet_name": definition["sheet_name"],
                        "table_name": definition["table_name"],
                        "inserted_rows": len(rows),
                        "replaced": replaced,
                        "columns": definition["columns"],
                    }
                )

            # One transaction: all tables or nothing.
            provider.execute_transaction(statements)

        finally:
            provider.disconnect()

        # The schema changed: forget the cached schema/sample values.
        schema_cache.invalidate(self.provider.value, self.database_url)

        return {
            "file_id": file_id,
            # send this as database_url to the SQL endpoints to ask questions
            "database_url": excel_database_url(self.project_id),
            "tables_created": len(summary),
            "total_rows_inserted": sum(t["inserted_rows"] for t in summary),
            "tables": summary,
        }