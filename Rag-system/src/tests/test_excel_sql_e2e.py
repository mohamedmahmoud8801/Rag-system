import pytest

from controllers.ProcessController import ProcessController
from controllers.ExcelSQLController import ExcelSQLController
from stores.sql.SQLProviderFactory import SQLProviderFactory
from stores.sql.SQLEnums import SQLProviderEnum


PROJECT_ID = "1"

FILE_ID = "ll6ebggns9fy_RAG_Evaluation_Tracker.xlsx"

POSTGRES_PASSWORD = "admin222"

POSTGRES_DATABASE_URL = (
    "postgresql+psycopg2://"
    f"postgres:{POSTGRES_PASSWORD}"
    "@localhost:5000/excel_ingest_test"
)
def get_excel_table_names(controller, sheets):
    table_names = []

    for index, sheet in enumerate(sheets):
        table_name = controller._sanitize_identifier(
            sheet["sheet_name"],
            fallback=f"sheet_{index + 1}",
        )
        table_names.append(table_name)

    return table_names

def test_real_excel_extraction():

    controller = ProcessController(
        project_id=PROJECT_ID
    )

    sheets = controller.get_excel_structured_content(
        file_id=FILE_ID
    )

    assert sheets is not None
    assert len(sheets) > 0

    for sheet in sheets:

        assert "sheet_name" in sheet
        assert "columns" in sheet
        assert "records" in sheet

        assert isinstance(
            sheet["columns"],
            list
        )

        assert isinstance(
            sheet["records"],
            list
        )

        print(
            f"\nSheet: {sheet['sheet_name']}"
        )

        print(
            f"Columns: {sheet['columns']}"
        )

        print(
            f"Rows: {sheet['row_count']}"
        )

        if sheet["records"]:
            print(
                f"First row: "
                f"{sheet['records'][0]}"
            )


@pytest.mark.asyncio
async def test_real_excel_sql_ingest():

    controller = ExcelSQLController(
        project_id=PROJECT_ID,
        provider=SQLProviderEnum.POSTGRESQL.value,
        database_url=POSTGRES_DATABASE_URL,
    )

    provider = SQLProviderFactory.create(
        provider=SQLProviderEnum.POSTGRESQL,
        database_url=POSTGRES_DATABASE_URL,
    )

    sheets = None
    table_names = []

    try:
        process_controller = ProcessController(
            project_id=PROJECT_ID
        )

        sheets = process_controller.get_excel_structured_content(
            file_id=FILE_ID
        )

        assert sheets is not None
        assert len(sheets) > 0

        # Use the exact same identifier rules as ExcelSQLController
        table_names = get_excel_table_names(
            controller,
            sheets,
        )

        # Cleanup before ingestion
        for table_name in table_names:
            provider.execute(
                query=f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
            )

        # Real Excel -> PostgreSQL ingestion
        result = await controller.ingest(
            file_id=FILE_ID
        )

        assert result is not None
        assert result["file_id"] == FILE_ID
        assert result["tables_created"] > 0
        assert result["total_rows_inserted"] > 0
        assert len(result["tables"]) > 0

        # Verify created tables and inserted data
        for table in result["tables"]:

            table_name = table["table_name"]

            query_result = provider.execute(
                query=f'SELECT * FROM "{table_name}"'
            )

            assert query_result["row_count"] > 0
            assert len(query_result["columns"]) > 0
            assert len(query_result["rows"]) > 0

            print(
                f"\nTable: {table_name}"
                f"\nColumns: {query_result['columns']}"
                f"\nRows: {query_result['row_count']}"
            )

    finally:

        # Cleanup after test
        for table_name in table_names:
            provider.execute(
                query=f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
            )

        provider.disconnect()