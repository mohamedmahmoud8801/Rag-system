import re
from types import SimpleNamespace

import pytest

from controllers.SQLController import SQLController
from stores.sql.SQLValidator import SQLValidationError


# ============================================================
# Helpers
# ============================================================

def normalize_sql(sql: str) -> str:
    """
    Normalize SQL only for test comparisons.

    The real controller intentionally places LIMIT on a new line,
    so tests must not depend on whitespace/newline formatting.
    """
    return re.sub(r"\s+", " ", sql.strip()).strip()


EXPECTED_LIMIT_SQL = (
    "SELECT question "
    "FROM rag_evaluation "
    "WHERE correct = '❌' "
    "LIMIT 10"
)


EXPECTED_SIMPLE_LIMIT_SQL = (
    "SELECT question "
    "FROM rag_evaluation "
    "LIMIT 10"
)


# ============================================================
# Fake SQL provider
# ============================================================

class FakeProvider:
    def __init__(self):
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True


# ============================================================
# Fake SQL model
# ============================================================

class FakeModel:
    def __init__(self):
        self.provider = FakeProvider()
        self.disconnected = False
        self.execute_calls = []

        self.schema = {
            "rag_evaluation": {
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                    },
                    {
                        "name": "question",
                        "type": "TEXT",
                    },
                    {
                        "name": "answer",
                        "type": "TEXT",
                    },
                    {
                        "name": "correct",
                        "type": "TEXT",
                    },
                    {
                        "name": "type",
                        "type": "TEXT",
                    },
                ],
                "foreign_keys": [],
            }
        }

        self.tables = [
            "rag_evaluation"
        ]

        self.result = {
            "columns": [
                "question",
                "correct",
                "type",
            ],
            "rows": [
                {
                    "question": "How many questions are correct?",
                    "correct": "✅",
                    "type": "factual",
                },
                {
                    "question": "How many questions are incorrect?",
                    "correct": "❌",
                    "type": "negative",
                },
            ],
        }

        self.execute_exception = None

    async def get_schema(self, tables=None):
        if tables:
            return {
                table: self.schema[table]
                for table in tables
                if table in self.schema
            }

        return self.schema

    async def get_tables(self):
        return self.tables

    async def execute(self, query):
        self.execute_calls.append(query)

        if self.execute_exception is not None:
            exception = self.execute_exception
            self.execute_exception = None
            raise exception

        return self.result

    async def disconnect(self):
        self.disconnected = True


# ============================================================
# Fake parser
# ============================================================

class FakeParser:
    def get(self, key, params=None):
        params = params or {}

        templates = {
            "system_prompt": (
                "You are a SQL generation engine."
            ),
            "schema_prompt": (
                "Database schema:\n"
                "{schema}"
            ),
            "footer_prompt": (
                "User question:\n"
                "{question}"
            ),
            "sql_generation": (
                "Generate SQL using this schema:\n"
                "{schema}\n"
                "Question: {question}"
            ),
            "sql_correction": (
                "Correct the SQL using:\n"
                "Schema: {schema}\n"
                "Question: {question}\n"
                "Error: {error}"
            ),
        }

        template = templates.get(
            key,
            key,
        )

        try:
            return template.format(**params)
        except (KeyError, IndexError):
            return template


# ============================================================
# Fake generation client
# ============================================================

class FakeGenerationClient:
    def __init__(
        self,
        generated_sql="SELECT * FROM rag_evaluation",
        corrected_sql="SELECT * FROM rag_evaluation",
        verifier_responses=None,
    ):
        self.generated_sql = generated_sql
        self.corrected_sql = corrected_sql
        self.verifier_responses = list(
            verifier_responses or []
        )

        self.calls = []

        self.enums = SimpleNamespace(
            SYSTEM=SimpleNamespace(
                value="system"
            ),
            USER=SimpleNamespace(
                value="user"
            ),
            ASSISTANT=SimpleNamespace(
                value="assistant"
            ),
        )

    def construct_prompt(
        self,
        prompt,
        role,
    ):
        return {
            "role": role,
            "content": prompt,
        }

    async def generate_text(
        self,
        prompt,
        chat_history=None,
        max_output_tokens=None,
        temperature=None,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "chat_history": chat_history,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            }
        )

        system_prompt = ""

        if chat_history:
            for message in chat_history:
                if (
                    message.get("role")
                    == self.enums.SYSTEM.value
                ):
                    system_prompt = str(
                        message.get(
                            "content",
                            "",
                        )
                    ).lower()

        # Semantic verifier
        if (
            "neutral sql semantic verifier"
            in system_prompt
        ):
            if self.verifier_responses:
                return self.verifier_responses.pop(0)

            return (
                '{"verdict":"PASS",'
                '"reason":"The SQL correctly answers the question."}'
            )

        # SQL correction
        if (
            "sql correction engine"
            in system_prompt
        ):
            return self.corrected_sql

        # Normal SQL generation
        return self.generated_sql


# ============================================================
# Controller builder
# ============================================================

def build_controller(
    monkeypatch,
    generated_sql="SELECT * FROM rag_evaluation",
    corrected_sql="SELECT * FROM rag_evaluation",
    verifier_responses=None,
):
    generation_client = FakeGenerationClient(
        generated_sql=generated_sql,
        corrected_sql=corrected_sql,
        verifier_responses=verifier_responses,
    )

    controller = SQLController(
        generation_client=generation_client,
        sql_template_parser=FakeParser(),
    )

    fake_model = FakeModel()

    async def fake_create_model(
        self,
        provider,
        database_url,
    ):
        return fake_model

    monkeypatch.setattr(
        SQLController,
        "_create_model",
        fake_create_model,
    )

    return (
        controller,
        fake_model,
        generation_client,
    )


# ============================================================
# SQL cleaning
# ============================================================

def test_clean_sql_removes_sql_fence():
    sql = """
    ```sql
    SELECT * FROM customers
    ```
    """

    result = SQLController._clean_sql(sql)

    assert result == "SELECT * FROM customers"


def test_clean_sql_removes_generic_fence():
    sql = """
    ```
    SELECT * FROM customers
    ```
    """

    result = SQLController._clean_sql(sql)

    assert result == "SELECT * FROM customers"


def test_clean_sql_preserves_normal_sql():
    sql = "SELECT * FROM customers"

    result = SQLController._clean_sql(sql)

    assert result == sql


def test_clean_sql_does_not_remove_think_tags():
    sql = """
    <think>
    I need to inspect the schema.
    </think>
    SELECT * FROM customers
    """

    result = SQLController._clean_sql(sql)

    assert "<think>" in result
    assert "</think>" in result
    assert "SELECT * FROM customers" in result


# ============================================================
# Semantic verification parser
# ============================================================

def test_parse_semantic_verification_pass():
    response = """
    {
        "verdict": "PASS",
        "reason": "The SQL correctly answers the question."
    }
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"
    assert (
        result["reason"]
        == "The SQL correctly answers the question."
    )


def test_parse_semantic_verification_fail():
    response = """
    {
        "verdict": "FAIL",
        "reason": "Wrong filter.",
        "correction_hint": "Use correct = '❌'."
    }
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "FAIL"
    assert result["reason"] == "Wrong filter."
    assert (
        result["correction_hint"]
        == "Use correct = '❌'."
    )


def test_parse_semantic_verification_embedded_json():
    response = """
    The verifier result is:

    {
        "verdict": "PASS",
        "reason": "Correct."
    }

    End.
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"
    assert result["reason"] == "Correct."


def test_parse_semantic_verification_markdown_json():
    response = """
    ```json
    {
        "verdict": "PASS",
        "reason": "Correct."
    }
    ```
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"


def test_parse_semantic_verification_think_block():
    response = """
    <think>
    I should verify the SQL.
    </think>

    {
        "verdict": "PASS",
        "reason": "Correct."
    }
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"


def test_parse_semantic_verification_malformed_fails_open():
    response = "This is not JSON."

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"
    assert result["verification_failed"] is True


def test_parse_semantic_verification_normalizes_verdict():
    response = """
    {
        "verdict": "pass",
        "reason": "Correct."
    }
    """

    result = (
        SQLController
        ._parse_semantic_verification(response)
    )

    assert result["verdict"] == "PASS"


# ============================================================
# Semantic contradiction detection
# ============================================================

def test_detect_contradiction_missing_filter_but_where_exists():
    semantic_check = {
        "verdict": "FAIL",
        "reason": "The SQL is missing a filter.",
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    WHERE correct = '❌'
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show incorrect questions",
            sql,
            semantic_check,
        )
    )

    assert result is True


def test_detect_contradiction_missing_column_but_selected():
    semantic_check = {
        "verdict": "FAIL",
        "reason": (
            "The SQL is missing column question."
        ),
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show questions",
            sql,
            semantic_check,
        )
    )

    assert result is True


def test_detect_contradiction_structured_conditions_match():
    semantic_check = {
        "verdict": "FAIL",
        "reason": "The filter is incorrect.",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE",
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE",
            }
        ],
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    WHERE correct = '❌'
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show incorrect questions",
            sql,
            semantic_check,
        )
    )

    assert result is True


def test_detect_contradiction_returns_false_for_real_mismatch():
    semantic_check = {
        "verdict": "FAIL",
        "reason": "Wrong condition.",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE",
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "✅",
                "polarity": "POSITIVE",
            }
        ],
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    WHERE correct = '✅'
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show incorrect questions",
            sql,
            semantic_check,
        )
    )

    assert result is False


def test_detect_contradiction_returns_false_when_no_where_and_no_claim():
    semantic_check = {
        "verdict": "FAIL",
        "reason": "Something else is wrong.",
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show questions",
            sql,
            semantic_check,
        )
    )

    assert result is False


def test_detect_contradiction_normalizes_condition_values():
    semantic_check = {
        "verdict": "FAIL",
        "reason": "Wrong condition.",
        "requested_conditions": [
            {
                "target": " correct ",
                "operator": " = ",
                "value": "'❌'",
                "polarity": " positive ",
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE",
            }
        ],
    }

    sql = """
    SELECT question
    FROM rag_evaluation
    WHERE correct = '❌'
    """

    result = (
        SQLController
        ._detect_verifier_contradiction(
            "Show incorrect questions",
            sql,
            semantic_check,
        )
    )

    assert result is True


# ============================================================
# Schema formatting
# ============================================================

def test_format_schema_contains_table_and_columns():
    controller = SQLController(
        generation_client=None,
        sql_template_parser=FakeParser(),
    )

    schema = {
        "customers": {
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                },
                {
                    "name": "name",
                    "type": "TEXT",
                },
            ],
            "foreign_keys": [],
        }
    }

    result = controller._format_schema(schema)

    assert "customers" in result
    assert "id" in result
    assert "name" in result


def test_format_schema_contains_sample_values():
    controller = SQLController(
        generation_client=None,
        sql_template_parser=FakeParser(),
    )

    schema = {
        "customers": {
            "columns": [
                {
                    "name": "country",
                    "type": "TEXT",
                    "sample_values": [
                        "Egypt",
                        "Saudi Arabia",
                    ],
                }
            ],
            "foreign_keys": [],
        }
    }

    result = controller._format_schema(schema)

    assert "Egypt" in result
    assert "Saudi Arabia" in result


def test_format_schema_contains_foreign_keys():
    controller = SQLController(
        generation_client=None,
        sql_template_parser=FakeParser(),
    )

    schema = {
        "orders": {
            "columns": [
                {
                    "name": "customer_id",
                    "type": "INTEGER",
                }
            ],
            "foreign_keys": [
                {
                    "column": "customer_id",
                    "references": (
                        "customers.id"
                    ),
                }
            ],
        }
    }

    result = controller._format_schema(schema)

    assert "customer_id" in result
    assert "customers.id" in result


# ============================================================
# Identifier quoting
# ============================================================

def test_quote_identifier():
    result = SQLController._quote_identifier(
        "customer_name"
    )

    assert result == '"customer_name"'


def test_quote_identifier_escapes_double_quotes():
    result = SQLController._quote_identifier(
        'customer"name'
    )

    assert result == '"customer""name"'


# ============================================================
# SQL model helpers
# ============================================================

@pytest.mark.asyncio
async def test_get_tables(monkeypatch):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(monkeypatch)

    result = await controller.get_tables(
        provider="sqlite",
        database_url="sqlite:///test.db",
    )

    assert result == [
        "rag_evaluation"
    ]


@pytest.mark.asyncio
async def test_get_schema(monkeypatch):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(monkeypatch)

    result = await controller.get_schema(
        provider="sqlite",
        database_url="sqlite:///test.db",
    )

    assert "rag_evaluation" in result
    assert "columns" in result["rag_evaluation"]


@pytest.mark.asyncio
async def test_enrich_schema_with_sample_values(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(monkeypatch)

    schema = {
        "rag_evaluation": {
            "columns": [
                {
                    "name": "correct",
                    "type": "TEXT",
                }
            ],
            "foreign_keys": [],
        }
    }

    result = (
        await controller
        ._enrich_schema_with_sample_values(
            provider="sqlite",
            database_url="sqlite:///test.db",
            schema=schema,
        )
    )

    assert "rag_evaluation" in result


# ============================================================
# Execute
# ============================================================

@pytest.mark.asyncio
async def test_execute_success(monkeypatch):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(monkeypatch)

    result = await controller.execute(
        provider="sqlite",
        database_url="sqlite:///test.db",
        query="SELECT * FROM rag_evaluation",
        max_rows=2,
    )

    assert "columns" in result
    assert "rows" in result
    assert len(result["rows"]) == 2


# ============================================================
# generate_sql
# ============================================================

@pytest.mark.asyncio
async def test_generate_sql(monkeypatch):
    generated_sql = """
    ```sql
    SELECT question
    FROM rag_evaluation
    ```
    """

    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        generated_sql=generated_sql,
    )

    schema = {
        "rag_evaluation": {
            "columns": [
                {
                    "name": "question",
                    "type": "TEXT",
                }
            ],
            "foreign_keys": [],
        }
    }

    async def fake_get_schema(
        provider,
        database_url,
        tables=None,
    ):
        return schema

    async def fake_enrich(
        provider,
        database_url,
        schema,
    ):
        return schema

    monkeypatch.setattr(
        controller,
        "get_schema",
        fake_get_schema,
    )

    monkeypatch.setattr(
        controller,
        "_enrich_schema_with_sample_values",
        fake_enrich,
    )

    result = await controller.generate_sql(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show the questions",
    )

    assert normalize_sql(result["sql"]) == (
        "SELECT question FROM rag_evaluation"
    )

    assert result["question"] == (
        "Show the questions"
    )

    assert "schema" in result
    assert "full_prompt" in result
    assert "chat_history" in result

    assert len(fake_llm.calls) >= 1


# ============================================================
# query helpers
# ============================================================

async def fake_generate_sql_for_query(
    provider,
    database_url,
    question,
    tables=None,
    max_rows=100,
):
    return {
        "question": question,
        "schema": {
            "rag_evaluation": {
                "columns": [
                    {
                        "name": "question",
                        "type": "TEXT",
                    },
                    {
                        "name": "correct",
                        "type": "TEXT",
                    },
                ],
                "foreign_keys": [],
            }
        },
        "sql": (
            "SELECT question "
            "FROM rag_evaluation "
            "WHERE correct = '❌'"
        ),
        "full_prompt": "",
        "chat_history": [],
    }


async def fake_execute_result(
    provider,
    database_url,
    query,
    max_rows=100,
):
    return {
        "columns": [
            "question"
        ],
        "rows": [
            {
                "question": (
                    "How many questions are incorrect?"
                )
            }
        ],
    }


# ============================================================
# query - semantic PASS
# ============================================================

@pytest.mark.asyncio
async def test_query_semantic_pass(monkeypatch):
    verifier_response = """
    {
        "verdict": "PASS",
        "reason": "The SQL correctly selects incorrect questions.",
        "correction_hint": "",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ]
    }
    """

    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        verifier_responses=[
            verifier_response
        ],
    )

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql_for_query,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show incorrect questions",
        max_rows=10,
        max_retries=2,
    )

    assert normalize_sql(result["sql"]) == (
        EXPECTED_LIMIT_SQL
    )

    assert result["attempts"] == 1
    assert result["errors"] == []


# ============================================================
# query - semantic FAIL then correction
# ============================================================

@pytest.mark.asyncio
async def test_query_semantic_fail_then_correction(
    monkeypatch,
):
    first_verifier = """
    {
        "verdict": "FAIL",
        "reason": "The SQL selects correct questions instead of incorrect questions.",
        "correction_hint": "Use correct = '❌'.",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "✅",
                "polarity": "POSITIVE"
            }
        ]
    }
    """

    second_verifier = """
    {
        "verdict": "PASS",
        "reason": "The corrected SQL selects incorrect questions.",
        "correction_hint": "",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ]
    }
    """

    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        corrected_sql=(
            "SELECT question "
            "FROM rag_evaluation "
            "WHERE correct = '❌'"
        ),
        verifier_responses=[
            first_verifier,
            second_verifier,
        ],
    )

    async def first_generate_sql(
        provider,
        database_url,
        question,
        tables=None,
        max_rows=100,
    ):
        return {
            "question": question,
            "schema": {
                "rag_evaluation": {
                    "columns": [
                        {
                            "name": "question",
                            "type": "TEXT",
                        },
                        {
                            "name": "correct",
                            "type": "TEXT",
                        },
                    ],
                    "foreign_keys": [],
                }
            },
            "sql": (
                "SELECT question "
                "FROM rag_evaluation "
                "WHERE correct = '✅'"
            ),
            "full_prompt": "",
            "chat_history": [],
        }

    monkeypatch.setattr(
        controller,
        "generate_sql",
        first_generate_sql,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show incorrect questions",
        max_rows=10,
        max_retries=2,
    )

    assert normalize_sql(result["sql"]) == (
        EXPECTED_LIMIT_SQL
    )

    assert result["attempts"] == 2

    assert len(result["errors"]) == 1
    assert (
        result["errors"][0]["stage"]
        == "semantic_validation"
    )


# ============================================================
# query - verifier contradiction
# ============================================================

@pytest.mark.asyncio
async def test_query_semantic_verifier_contradiction(
    monkeypatch,
):
    verifier_response = """
    {
        "verdict": "FAIL",
        "reason": "The query is missing a filter.",
        "correction_hint": "",
        "requested_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ],
        "sql_conditions": [
            {
                "target": "correct",
                "operator": "=",
                "value": "❌",
                "polarity": "POSITIVE"
            }
        ]
    }
    """

    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        verifier_responses=[
            verifier_response
        ],
    )

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql_for_query,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show incorrect questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 1

    assert normalize_sql(result["sql"]) == (
        EXPECTED_LIMIT_SQL
    )

    assert result["errors"] == []


# ============================================================
# query - validation failure then correction
# ============================================================

@pytest.mark.asyncio
async def test_query_validation_failure_then_correction(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        corrected_sql=(
            "SELECT question "
            "FROM rag_evaluation"
        ),
        verifier_responses=[
            """
            {
                "verdict": "PASS",
                "reason": "The corrected SQL is valid.",
                "correction_hint": ""
            }
            """
        ],
    )

    async def fake_generate_sql(
        provider,
        database_url,
        question,
        tables=None,
        max_rows=100,
    ):
        return {
            "question": question,
            "schema": {
                "rag_evaluation": {
                    "columns": [
                        {
                            "name": "question",
                            "type": "TEXT",
                        }
                    ],
                    "foreign_keys": [],
                }
            },
            "sql": (
                "DELETE FROM rag_evaluation"
            ),
            "full_prompt": "",
            "chat_history": [],
        }

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    original_validate = (
        controller.sql_validator.validate
    )

    call_count = {
        "value": 0
    }

    def fake_validate(
        query,
        schema,
        max_rows,
    ):
        call_count["value"] += 1

        if call_count["value"] == 1:
            raise SQLValidationError(
                "Only SELECT queries are allowed."
            )

        return original_validate(
            query=query,
            schema=schema,
            max_rows=max_rows,
        )

    monkeypatch.setattr(
        controller.sql_validator,
        "validate",
        fake_validate,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 2

    assert (
        result["errors"][0]["stage"]
        == "validation"
    )

    assert normalize_sql(result["sql"]) == (
        EXPECTED_SIMPLE_LIMIT_SQL
    )


# ============================================================
# query - execution failure then correction
# ============================================================

@pytest.mark.asyncio
async def test_query_execution_failure_then_correction(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        corrected_sql=(
            "SELECT question "
            "FROM rag_evaluation"
        ),
        verifier_responses=[
            """
            {
                "verdict": "PASS",
                "reason": "The corrected SQL is correct.",
                "correction_hint": ""
            }
            """
        ],
    )

    async def fake_generate_sql(
        provider,
        database_url,
        question,
        tables=None,
        max_rows=100,
    ):
        return {
            "question": question,
            "schema": {
                "rag_evaluation": {
                    "columns": [
                        {
                            "name": "question",
                            "type": "TEXT",
                        }
                    ],
                    "foreign_keys": [],
                }
            },
            "sql": (
                "SELECT question "
                "FROM rag_evaluation"
            ),
            "full_prompt": "",
            "chat_history": [],
        }

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql,
    )

    execution_count = {
        "value": 0
    }

    async def fake_execute(
        provider,
        database_url,
        query,
        max_rows=100,
    ):
        execution_count["value"] += 1

        if execution_count["value"] == 1:
            raise Exception(
                "no such column: question"
            )

        return {
            "columns": [
                "question"
            ],
            "rows": [
                {
                    "question": "Test question"
                }
            ],
        }

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 2

    assert (
        result["errors"][0]["stage"]
        == "execution"
    )

    assert normalize_sql(result["sql"]) == (
        EXPECTED_SIMPLE_LIMIT_SQL
    )


# ============================================================
# query - malformed semantic verifier
# ============================================================

@pytest.mark.asyncio
async def test_query_malformed_semantic_verifier_fails_open(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        verifier_responses=[
            "This is not JSON."
        ],
    )

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql_for_query,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 1
    assert result["errors"] == []

    assert normalize_sql(result["sql"]) == (
        EXPECTED_LIMIT_SQL
    )


# ============================================================
# query - semantic verifier internal error
# ============================================================

@pytest.mark.asyncio
async def test_query_semantic_verifier_internal_error_fails_open(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(monkeypatch)

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql_for_query,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    async def broken_verifier(
        question,
        sql,
        schema,
        result,
    ):
        raise RuntimeError(
            "Verifier unavailable"
        )

    monkeypatch.setattr(
        controller,
        "_verify_sql_semantics",
        broken_verifier,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 1
    assert result["errors"] == []

    assert normalize_sql(result["sql"]) == (
        EXPECTED_LIMIT_SQL
    )


# ============================================================
# query - semantic failure after max retries
# ============================================================

@pytest.mark.asyncio
async def test_query_semantic_failure_after_max_retries(
    monkeypatch,
):
    (
        controller,
        fake_model,
        fake_llm,
    ) = build_controller(
        monkeypatch,
        verifier_responses=[
            """
            {
                "verdict": "FAIL",
                "reason": "Wrong semantic condition.",
                "correction_hint": "Use another condition."
            }
            """,
            """
            {
                "verdict": "FAIL",
                "reason": "Still semantically incorrect.",
                "correction_hint": "Correct the filter."
            }
            """,
            """
            {
                "verdict": "FAIL",
                "reason": "Still incorrect.",
                "correction_hint": ""
            }
            """,
        ],
    )

    monkeypatch.setattr(
        controller,
        "generate_sql",
        fake_generate_sql_for_query,
    )

    monkeypatch.setattr(
        controller,
        "execute",
        fake_execute_result,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///test.db",
        question="Show incorrect questions",
        max_rows=10,
        max_retries=2,
    )

    assert result["attempts"] == 3

    assert len(result["errors"]) == 3

    assert all(
        error["stage"]
        == "semantic_validation"
        for error in result["errors"]
    )
    