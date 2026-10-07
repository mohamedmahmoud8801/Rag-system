import os

import pytest

from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLProviderFactory import SQLProviderFactory


POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_TEST_PASSWORD",
    "admin222",
)

DATABASE_URL = (
    "postgresql+psycopg2://"
    f"postgres:{POSTGRES_PASSWORD}"
    "@localhost:5000/sql_provider_test"
)


@pytest.fixture
def provider():
    provider = SQLProviderFactory.create(
        provider=SQLProviderEnum.POSTGRESQL,
        database_url=DATABASE_URL,
    )

    yield provider

    provider.disconnect()


def test_validate_connection(provider):
    assert provider.validate_connection() is True


def test_get_tables(provider):
    tables = provider.get_tables()

    assert isinstance(tables, list)
    assert "rag_evaluation" in tables


def test_get_schema(provider):
    schema = provider.get_schema(
        tables=["rag_evaluation"]
    )

    assert "rag_evaluation" in schema

    table_schema = schema["rag_evaluation"]

    assert "columns" in table_schema
    assert "foreign_keys" in table_schema

    column_names = {
        column["name"]
        for column in table_schema["columns"]
    }

    assert "column_number" in column_names


def test_execute_select(provider):
    result = provider.execute(
        query="""
            SELECT *
            FROM rag_evaluation
            LIMIT 2
        """
    )

    assert result["columns"]
    assert isinstance(result["rows"], list)
    assert result["row_count"] == len(result["rows"])


def test_execute_parameterized_query(provider):
    result = provider.execute(
        query="""
            SELECT *
            FROM rag_evaluation
            WHERE type = :question_type
            LIMIT 5
        """,
        params={
            "question_type": "factual"
        },
    )

    assert result["columns"]
    assert isinstance(result["rows"], list)

    for row in result["rows"]:
        assert row["type"] == "factual"


def test_execute_count(provider):
    result = provider.execute(
        query="""
            SELECT COUNT(*) AS total
            FROM rag_evaluation
        """
    )

    assert result["columns"] == ["total"]
    assert len(result["rows"]) == 1
    assert result["row_count"] == 1
    assert result["rows"][0]["total"] >= 0


def test_disconnect(provider):
    provider.connect()

    assert provider.engine is not None

    provider.disconnect()

    assert provider.engine is None