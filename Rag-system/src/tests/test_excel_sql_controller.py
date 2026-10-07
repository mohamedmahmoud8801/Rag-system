import asyncio
import uuid

from controllers.ExcelSQLController import ExcelSQLController
from stores.sql.SQLProviderFactory import SQLProviderFactory
from stores.sql.SQLEnums import SQLProviderEnum


POSTGRES_PASSWORD = "admin222"

POSTGRES_DATABASE_URL = (
    "postgresql+psycopg2://"
    f"postgres:{POSTGRES_PASSWORD}"
    "@localhost:5000/excel_ingest_test"
)


def create_controller():
    return ExcelSQLController(
        project_id="test_project",
        provider="sqlite",
        database_url="sqlite:///:memory:",
    )


def test_sanitize_identifier_basic():
    controller = create_controller()

    assert (
        controller._sanitize_identifier(
            "Customer Name",
            "column_1",
        )
        == "customer_name"
    )


def test_sanitize_identifier_special_characters():
    controller = create_controller()

    assert (
        controller._sanitize_identifier(
            "Total Sales ($)",
            "column_1",
        )
        == "total_sales"
    )


def test_sanitize_identifier_starts_with_number():
    controller = create_controller()

    assert (
        controller._sanitize_identifier(
            "123 Sales",
            "column_1",
        )
        == "column_123_sales"
    )


def test_sanitize_identifier_hash_column():
    controller = create_controller()

    assert (
        controller._sanitize_identifier(
            "#",
            "column_1",
        )
        == "column_number"
    )


def test_sanitize_identifier_empty_value_uses_fallback():
    controller = create_controller()

    assert (
        controller._sanitize_identifier(
            "",
            "column_1",
        )
        == "column_1"
    )


def test_infer_integer_type():
    controller = create_controller()

    assert (
        controller._infer_type(
            [1, 2, 3]
        )
        == "INTEGER"
    )


def test_infer_float_type():
    controller = create_controller()

    assert (
        controller._infer_type(
            [1.5, 2.5, 3.5]
        )
        == "FLOAT"
    )


def test_infer_mixed_numeric_type():
    controller = create_controller()

    assert (
        controller._infer_type(
            [1, 2.5, 3]
        )
        == "FLOAT"
    )


def test_infer_boolean_type():
    controller = create_controller()

    assert (
        controller._infer_type(
            [True, False, True]
        )
        == "BOOLEAN"
    )


def test_infer_text_type():
    controller = create_controller()

    assert (
        controller._infer_type(
            ["Ahmed", "Sara", "Mohamed"]
        )
        == "TEXT"
    )


def test_infer_empty_values():
    controller = create_controller()

    assert (
        controller._infer_type([])
        == "TEXT"
    )


def test_infer_values_with_none():
    controller = create_controller()

    assert (
        controller._infer_type(
            [None, 1, 2, 3]
        )
        == "INTEGER"
    )


def test_build_table_definition_basic():
    controller = create_controller()

    sheet = {
        "sheet_name": "Customers",
        "columns": [
            "Name",
            "Age",
            "Balance",
        ],
        "records": [
            {
                "Name": "Ahmed",
                "Age": 25,
                "Balance": 1500.5,
            },
            {
                "Name": "Sara",
                "Age": 30,
                "Balance": 2200.75,
            },
        ],
    }

    definition = controller._build_table_definition(sheet)

    assert definition["sheet_name"] == "Customers"
    assert definition["row_count"] == 2

    assert definition["columns"] == [
        {
            "original_name": "Name",
            "name": "name",
            "type": "TEXT",
        },
        {
            "original_name": "Age",
            "name": "age",
            "type": "INTEGER",
        },
        {
            "original_name": "Balance",
            "name": "balance",
            "type": "FLOAT",
        },
    ]


def test_build_table_definition_hash_column():
    controller = create_controller()

    sheet = {
        "sheet_name": "Evaluation",
        "columns": ["#", "Question"],
        "records": [
            {
                "#": 1,
                "Question": "What is AI?",
            },
            {
                "#": 2,
                "Question": "What is RAG?",
            },
        ],
    }

    definition = controller._build_table_definition(sheet)

    assert definition["columns"][0] == {
        "original_name": "#",
        "name": "column_number",
        "type": "INTEGER",
    }


def test_build_table_definition_duplicate_sanitized_names():
    controller = create_controller()

    sheet = {
        "sheet_name": "Test",
        "columns": [
            "Customer Name",
            "Customer-Name",
            "Customer_Name",
        ],
        "records": [
            {
                "Customer Name": "Ahmed",
                "Customer-Name": "Ali",
                "Customer_Name": "Mohamed",
            },
        ],
    }

    definition = controller._build_table_definition(sheet)

    names = [
        column["name"]
        for column in definition["columns"]
    ]

    assert names == [
        "customer_name",
        "customer_name_2",
        "customer_name_3",
    ]


def test_build_table_definition_numeric_column_name():
    controller = create_controller()

    sheet = {
        "sheet_name": "Sales",
        "columns": [
            "2025 Sales",
        ],
        "records": [
            {
                "2025 Sales": 100,
            },
        ],
    }

    definition = controller._build_table_definition(sheet)

    assert definition["columns"][0]["name"] == (
        "column_2025_sales"
    )


def test_build_table_definition_empty_records():
    controller = create_controller()

    sheet = {
        "sheet_name": "EmptySheet",
        "columns": [
            "Name",
            "Age",
        ],
        "records": [],
    }

    definition = controller._build_table_definition(sheet)

    assert definition["sheet_name"] == "EmptySheet"
    assert definition["row_count"] == 0

    assert definition["columns"] == [
        {
            "original_name": "Name",
            "name": "name",
            "type": "TEXT",
        },
        {
            "original_name": "Age",
            "name": "age",
            "type": "TEXT",
        },
    ]


def test_build_create_table_sql():
    controller = create_controller()

    columns = [
        {
            "name": "name",
            "type": "TEXT",
        },
        {
            "name": "age",
            "type": "INTEGER",
        },
        {
            "name": "balance",
            "type": "FLOAT",
        },
    ]

    sql = controller._build_create_table_sql(
        table_name="Customers",
        columns=columns,
    )

    assert sql == (
        "CREATE TABLE customers "
        "(name TEXT, age INTEGER, balance FLOAT)"
    )


def test_build_create_table_sql_sanitizes_table_name():
    controller = create_controller()

    columns = [
        {
            "name": "name",
            "type": "TEXT",
        },
    ]

    sql = controller._build_create_table_sql(
        table_name="Customer Data 2025",
        columns=columns,
    )

    assert sql == (
        "CREATE TABLE customer_data_2025 "
        "(name TEXT)"
    )


def test_build_create_table_sql_empty_columns():
    controller = create_controller()

    sql = controller._build_create_table_sql(
        table_name="EmptyTable",
        columns=[],
    )

    assert sql == "CREATE TABLE emptytable ()"


class FakeProcessController:

    def __init__(self, sheets):
        self.sheets = sheets

    def get_excel_structured_content(self, file_id):
        return self.sheets


def create_postgres_controller(sheets):
    controller = ExcelSQLController(
        project_id="excel_test_project",
        provider="postgresql",
        database_url=POSTGRES_DATABASE_URL,
    )

    controller.process_controller = FakeProcessController(
        sheets=sheets
    )

    return controller


def create_unique_table_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def drop_table(table_name):
    provider = SQLProviderFactory.create(
        provider=SQLProviderEnum.POSTGRESQL,
        database_url=POSTGRES_DATABASE_URL,
    )

    try:
        provider.execute(
            query=f'DROP TABLE IF EXISTS "{table_name}"'
        )
    finally:
        provider.disconnect()


def test_create_tables_postgresql():
    controller = create_postgres_controller([])

    table_name = create_unique_table_name(
        "excel_create_test"
    )

    definitions = [
        {
            "sheet_name": table_name,
            "columns": [
                {
                    "original_name": "Name",
                    "name": "name",
                    "type": "TEXT",
                },
                {
                    "original_name": "Age",
                    "name": "age",
                    "type": "INTEGER",
                },
            ],
            "row_count": 0,
        }
    ]

    try:
        result = controller._create_tables(
            definitions=definitions
        )

        assert len(result) == 1
        assert result[0]["table_name"] == table_name

        provider = SQLProviderFactory.create(
            provider=SQLProviderEnum.POSTGRESQL,
            database_url=POSTGRES_DATABASE_URL,
        )

        try:
            tables = provider.get_tables()

            assert table_name in tables

            schema = provider.get_schema(
                tables=[table_name]
            )

            assert table_name in schema

            column_names = {
                column["name"]
                for column in schema[table_name]["columns"]
            }

            assert column_names == {
                "name",
                "age",
            }

        finally:
            provider.disconnect()

    finally:
        drop_table(table_name)


def test_insert_rows_postgresql():
    table_name = create_unique_table_name(
        "excel_insert_test"
    )

    sheets = [
        {
            "sheet_name": table_name,
            "columns": [
                "Name",
                "Age",
                "Country",
            ],
            "records": [
                {
                    "Name": "Ahmed",
                    "Age": 25,
                    "Country": "Egypt",
                },
                {
                    "Name": "Sara",
                    "Age": 30,
                    "Country": "Egypt",
                },
            ],
        }
    ]

    controller = create_postgres_controller(
        sheets
    )

    definitions = controller._build_table_definition(
        sheets[0]
    )

    try:
        controller._create_tables(
            definitions=[definitions]
        )

        result = controller._insert_rows(
            file_id="test_file",
            definitions=[definitions],
        )

        assert result == [
            {
                "sheet_name": table_name,
                "table_name": table_name,
                "inserted_rows": 2,
            }
        ]

        provider = SQLProviderFactory.create(
            provider=SQLProviderEnum.POSTGRESQL,
            database_url=POSTGRES_DATABASE_URL,
        )

        try:
            data = provider.execute(
                query=(
                    f"SELECT name, age, country "
                    f"FROM {table_name} "
                    f"ORDER BY age"
                )
            )

            assert data["row_count"] == 2

            assert data["rows"] == [
                {
                    "name": "Ahmed",
                    "age": 25,
                    "country": "Egypt",
                },
                {
                    "name": "Sara",
                    "age": 30,
                    "country": "Egypt",
                },
            ]

        finally:
            provider.disconnect()

    finally:
        drop_table(table_name)


def test_insert_rows_handles_special_characters():
    table_name = create_unique_table_name(
        "excel_special_test"
    )

    sheets = [
        {
            "sheet_name": table_name,
            "columns": [
                "Name",
                "Comment",
            ],
            "records": [
                {
                    "Name": "O'Brien",
                    "Comment": "It's a test",
                },
                {
                    "Name": "Ahmed",
                    "Comment": "10% increase",
                },
            ],
        }
    ]

    controller = create_postgres_controller(
        sheets
    )

    definitions = controller._build_table_definition(
        sheets[0]
    )

    try:
        controller._create_tables(
            definitions=[definitions]
        )

        result = controller._insert_rows(
            file_id="test_file",
            definitions=[definitions],
        )

        assert result[0]["inserted_rows"] == 2

        provider = SQLProviderFactory.create(
            provider=SQLProviderEnum.POSTGRESQL,
            database_url=POSTGRES_DATABASE_URL,
        )

        try:
            data = provider.execute(
                query=(
                    f"SELECT name, comment "
                    f"FROM {table_name} "
                    f"ORDER BY name"
                )
            )

            assert data["row_count"] == 2

            comments = {
                row["comment"]
                for row in data["rows"]
            }

            assert comments == {
                "It's a test",
                "10% increase",
            }

        finally:
            provider.disconnect()

    finally:
        drop_table(table_name)


def test_ingest_end_to_end_postgresql():
    table_name = create_unique_table_name(
        "excel_e2e_test"
    )

    sheets = [
        {
            "sheet_name": table_name,
            "columns": [
                "Name",
                "Age",
            ],
            "records": [
                {
                    "Name": "Ahmed",
                    "Age": 25,
                },
                {
                    "Name": "Sara",
                    "Age": 30,
                },
                {
                    "Name": "Mohamed",
                    "Age": 28,
                },
            ],
        }
    ]

    controller = create_postgres_controller(
        sheets
    )

    try:
        result = asyncio.run(
            controller.ingest(
                file_id="excel_test_file"
            )
        )

        assert result["file_id"] == "excel_test_file"
        assert result["tables_created"] == 1
        assert result["total_rows_inserted"] == 3

        assert result["tables"] == [
            {
                "sheet_name": table_name,
                "table_name": table_name,
                "inserted_rows": 3,
            }
        ]

        provider = SQLProviderFactory.create(
            provider=SQLProviderEnum.POSTGRESQL,
            database_url=POSTGRES_DATABASE_URL,
        )

        try:
            data = provider.execute(
                query=f"SELECT COUNT(*) AS count FROM {table_name}"
            )

            assert data["rows"][0]["count"] == 3

        finally:
            provider.disconnect()

    finally:
        drop_table(table_name)



def test_ingest_multiple_sheets_postgresql():
    table_name_1 = create_unique_table_name(
        "excel_customers"
    )
    table_name_2 = create_unique_table_name(
        "excel_products"
    )

    sheets = [
        {
            "sheet_name": table_name_1,
            "columns": [
                "Name",
                "Country",
            ],
            "records": [
                {
                    "Name": "Ahmed",
                    "Country": "Egypt",
                },
                {
                    "Name": "Sara",
                    "Country": "Egypt",
                },
            ],
        },
        {
            "sheet_name": table_name_2,
            "columns": [
                "Product",
                "Price",
            ],
            "records": [
                {
                    "Product": "Laptop",
                    "Price": 1500.0,
                },
                {
                    "Product": "Phone",
                    "Price": 800.0,
                },
                {
                    "Product": "Tablet",
                    "Price": 500.0,
                },
            ],
        },
    ]

    controller = create_postgres_controller(
        sheets
    )

    try:
        result = asyncio.run(
            controller.ingest(
                file_id="multi_sheet_test"
            )
        )

        assert result["file_id"] == "multi_sheet_test"
        assert result["tables_created"] == 2
        assert result["total_rows_inserted"] == 5

        assert len(result["tables"]) == 2

        assert result["tables"][0]["table_name"] == table_name_1
        assert result["tables"][0]["inserted_rows"] == 2

        assert result["tables"][1]["table_name"] == table_name_2
        assert result["tables"][1]["inserted_rows"] == 3

        provider = SQLProviderFactory.create(
            provider=SQLProviderEnum.POSTGRESQL,
            database_url=POSTGRES_DATABASE_URL,
        )

        try:
            customers = provider.execute(
                query=f"""
                    SELECT COUNT(*) AS count
                    FROM {table_name_1}
                """
            )

            products = provider.execute(
                query=f"""
                    SELECT COUNT(*) AS count
                    FROM {table_name_2}
                """
            )

            assert customers["rows"][0]["count"] == 2
            assert products["rows"][0]["count"] == 3

        finally:
            provider.disconnect()

    finally:
        drop_table(table_name_1)
        drop_table(table_name_2)


def test_create_tables_duplicate_sanitized_table_names():
    controller = create_postgres_controller([])

    definitions = [
        {
            "sheet_name": "Customer Data",
            "columns": [
                {
                    "original_name": "Name",
                    "name": "name",
                    "type": "TEXT",
                },
            ],
            "row_count": 1,
        },
        {
            "sheet_name": "Customer-Data",
            "columns": [
                {
                    "original_name": "Name",
                    "name": "name",
                    "type": "TEXT",
                },
            ],
            "row_count": 1,
        },
    ]

    try:
        controller._create_tables(
            definitions=definitions
        )

    except Exception as exc:
        assert "already exists" in str(exc).lower()

    finally:
        drop_table("customer_data")

def test_ingest_empty_columns_fails():
    table_name = create_unique_table_name(
        "excel_empty_columns"
    )

    sheets = [
        {
            "sheet_name": table_name,
            "columns": [],
            "records": [
                {},
            ],
        }
    ]

    controller = create_postgres_controller(
        sheets
    )

    try:
        try:
            asyncio.run(
                controller.ingest(
                    file_id="empty_columns_test"
                )
            )

            assert False, (
                "Expected ingestion to fail for "
                "empty columns"
            )

        except Exception:
            pass

    finally:
        drop_table(table_name)


