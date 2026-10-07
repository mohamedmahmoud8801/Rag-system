from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from ..SQLInterface import SQLInterface


class SQLiteProvider(SQLInterface):

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Optional[Engine] = None

    def connect(self) -> None:

        if self.engine is None:
            self.engine = create_engine(
                self.database_url,
                future=True,
                pool_pre_ping=True,
            )

    def disconnect(self) -> None:

        if self.engine is not None:
            self.engine.dispose()
            self.engine = None

    def validate_connection(self) -> bool:

        try:
            self.connect()

            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return True

        except Exception:
            return False

    def get_tables(self) -> List[str]:

        self.connect()

        inspector = inspect(self.engine)

        return inspector.get_table_names()

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

            tables = [
                table
                for table in tables
                if table in available_tables
            ]

        schema = {}

        for table_name in tables:

            # ==========================================
            # Columns
            # ==========================================

            columns = inspector.get_columns(
                table_name
            )

            # ==========================================
            # Primary Keys
            # ==========================================

            primary_key_columns = inspector.get_pk_constraint(
                table_name
            ).get(
                "constrained_columns",
                []
            )

            # ==========================================
            # Foreign Keys
            # ==========================================

            foreign_keys = inspector.get_foreign_keys(
                table_name
            )

            schema[table_name] = {

                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column.get(
                            "nullable",
                            True
                        ),
                        "primary_key": (
                            column["name"]
                            in primary_key_columns
                        ),
                    }
                    for column in columns
                ],

                "foreign_keys": [
                    {
                        "column": column_name,
                        "references_table": fk.get(
                            "referred_table"
                        ),
                        "references_column": (
                            fk.get(
                                "referred_columns",
                                [None]
                            )[0]
                        ),
                    }
                    for fk in foreign_keys
                    for column_name in fk.get(
                        "constrained_columns",
                        []
                    )
                ],
            }

        return schema

    def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        self.connect()

        with self.engine.connect() as connection:

            result = connection.execute(
                text(query),
                params or {}
            )

            columns = list(result.keys())

            rows = [
                dict(row)
                for row in result.mappings().all()
            ]

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }

