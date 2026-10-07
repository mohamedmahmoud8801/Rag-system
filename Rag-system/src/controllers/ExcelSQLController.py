import re
from typing import Any, Dict, List

from controllers.ProcessController import ProcessController
from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLProviderFactory import SQLProviderFactory


class ExcelSQLController:

    def __init__(
        self,
        project_id: str,
        provider: str,
        database_url: str
    ):
        self.project_id = project_id
        self.provider = SQLProviderEnum(
            provider.lower()
        )
        self.database_url = database_url

        self.process_controller = ProcessController(
            project_id=project_id
        )

    def _sanitize_identifier(
    self,
    value: str,
    fallback: str
) -> str:

        original_value = str(value).strip()

        if original_value == "#":
            return "column_number"

        value = original_value.lower()

        value = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            value
        )

        value = re.sub(
            r"_+",
            "_",
            value
        )

        value = value.strip("_")

        if not value:
            value = fallback

        if value[0].isdigit():
            value = f"column_{value}"

        return value

    def _infer_type(
        self,
        values: List[Any]
    ) -> str:

        non_null_values = [
            value
            for value in values
            if value is not None
        ]

        if not non_null_values:
            return "TEXT"

        types = set()

        for value in non_null_values:

            if isinstance(value, bool):
                types.add("BOOLEAN")

            elif isinstance(value, int):
                types.add("INTEGER")

            elif isinstance(value, float):
                types.add("FLOAT")

            else:
                types.add("TEXT")

        if types == {"INTEGER"}:
            return "INTEGER"

        if types.issubset(
            {"INTEGER", "FLOAT"}
        ):
            return "FLOAT"

        if types == {"BOOLEAN"}:
            return "BOOLEAN"

        return "TEXT"

    def _build_table_definition(
        self,
        sheet: Dict[str, Any]
    ) -> Dict[str, Any]:

        columns = sheet["columns"]
        records = sheet["records"]

        column_definitions = []

        used_names = set()

        for index, column in enumerate(columns):

            column_name = self._sanitize_identifier(
                column,
                fallback=f"column_{index + 1}"
            )

            original_name = column_name
            counter = 2

            while column_name in used_names:

                column_name = (
                    f"{original_name}_{counter}"
                )

                counter += 1

            used_names.add(column_name)

            values = [
                record.get(column)
                for record in records
            ]

            sql_type = self._infer_type(
                values
            )

            column_definitions.append(
                {
                    "original_name": column,
                    "name": column_name,
                    "type": sql_type,
                }
            )

        return {
            "sheet_name": sheet["sheet_name"],
            "columns": column_definitions,
            "row_count": len(records),
        }

    async def preview(
        self,
        file_id: str
    ) -> List[Dict[str, Any]]:

        sheets = (
            self.process_controller
            .get_excel_structured_content(
                file_id=file_id
            )
        )

        if sheets is None:
            raise ValueError(
                "Failed to extract Excel data"
            )

        result = []

        for sheet in sheets:

            definition = (
                self._build_table_definition(
                    sheet
                )
            )

            result.append(
                definition
            )

        return result
    def _build_create_table_sql(
    self,
    table_name: str,
    columns: list
) -> str:

        safe_table_name = self._sanitize_identifier(
            table_name,
            fallback="excel_table"
        )

        column_definitions = []

        for column in columns:

            column_definitions.append(
                f"{column['name']} {column['type']}"
            )

        return (
            f"CREATE TABLE {safe_table_name} "
            f"({', '.join(column_definitions)})"
        )


    def _create_tables(
    self,
    definitions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

        provider = SQLProviderFactory.create(
            provider=self.provider,
            database_url=self.database_url
        )

        results = []

        try:
            for definition in definitions:

                table_name = self._sanitize_identifier(
                    definition["sheet_name"],
                    fallback="excel_table"
                )

                sql = self._build_create_table_sql(
                    table_name=table_name,
                    columns=definition["columns"]
                )

                provider.execute(sql)

                results.append(
                    {
                        "sheet_name": definition["sheet_name"],
                        "table_name": table_name,
                        "sql": sql,
                        "row_count": definition["row_count"],
                    }
                )

            return results

        finally:
            provider.disconnect()


    def _insert_rows(
    self,
    file_id: str,
    definitions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

        sheets = (
            self.process_controller
            .get_excel_structured_content(
                file_id=file_id
            )
        )

        if sheets is None:
            raise ValueError(
                "Failed to extract Excel data"
            )

        provider = SQLProviderFactory.create(
            provider=self.provider,
            database_url=self.database_url
        )

        results = []

        try:

            for definition in definitions:

                sheet_name = definition["sheet_name"]

                # ------------------------------------------
                # Find original Excel sheet
                # ------------------------------------------

                sheet = next(
                    (
                        item
                        for item in sheets
                        if item["sheet_name"] == sheet_name
                    ),
                    None
                )

                if sheet is None:
                    raise ValueError(
                        f"Sheet not found: {sheet_name}"
                    )

                table_name = self._sanitize_identifier(
                    sheet_name,
                    fallback="excel_table"
                )

                columns = definition["columns"]
                records = sheet["records"]

                inserted_rows = 0

                # ------------------------------------------
                # Insert each Excel row
                # ------------------------------------------

                for row_index, record in enumerate(
                    records,
                    start=1
                ):

                    column_names = []
                    parameter_names = []
                    params = {}

                    for column_index, column in enumerate(
                        columns,
                        start=1
                    ):

                        original_name = column[
                            "original_name"
                        ]

                        sql_column_name = column[
                            "name"
                        ]

                        column_names.append(
                            sql_column_name
                        )

                        parameter_name = (
                            f"p_{row_index}_{column_index}"
                        )

                        parameter_names.append(
                            f":{parameter_name}"
                        )

                        params[parameter_name] = (
                            record.get(
                                original_name
                            )
                        )

                    sql = (
                        f"INSERT INTO {table_name} "
                        f"({', '.join(column_names)}) "
                        f"VALUES ({', '.join(parameter_names)})"
                    )

                    provider.execute(
                        query=sql,
                        params=params
                    )

                    inserted_rows += 1

                results.append(
                    {
                        "sheet_name": sheet_name,
                        "table_name": table_name,
                        "inserted_rows": inserted_rows,
                    }
                )

            return results

        finally:
            provider.disconnect()

    async def ingest(
    self,
    file_id: str
) -> Dict[str, Any]:

        # ==========================================
        # 1. Build table definitions
        # ==========================================

        definitions = await self.preview(
            file_id=file_id
        )

        if not definitions:
            raise ValueError(
                "No Excel table definitions found"
            )

        # ==========================================
        # 2. Create SQL tables
        # ==========================================

        created_tables = self._create_tables(
            definitions=definitions
        )

        # ==========================================
        # 3. Insert Excel rows
        # ==========================================

        inserted_rows = self._insert_rows(
            file_id=file_id,
            definitions=definitions
        )

        # ==========================================
        # 4. Calculate total rows
        # ==========================================

        total_rows = sum(
            item["inserted_rows"]
            for item in inserted_rows
        )

        # ==========================================
        # 5. Return ingestion summary
        # ==========================================

        return {
            "file_id": file_id,
            "tables_created": len(
                created_tables
            ),
            "total_rows_inserted": total_rows,
            "tables": inserted_rows,
        }