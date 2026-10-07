import pytest

from controllers.SQLController import SQLController
from stores.sql.templates import SQLTemplateParser


class FakeGenerationClient:

    class _Enums:

        class SYSTEM:
            value = "system"

    def __init__(self):
        self.enums = self._Enums()
        self.calls = 0

    def construct_prompt(self, prompt, role):
        return {
            "prompt": prompt,
            "role": role,
        }

    def generate_text(
        self,
        prompt,
        chat_history=None,
        max_output_chars=None,
        temperature=None,
        **kwargs,
    ):
        self.calls += 1

        # First generation -> intentionally invalid SQL
        if self.calls == 1:
            return "SELECT customer_name FROM customers"

        # Second generation -> corrected SQL
        if self.calls == 2:
            return "SELECT name FROM customers"

        # Third generation -> semantic verification
        if self.calls == 3:
            return (
                '{"verdict": "PASS", '
                '"reason": "The SQL correctly answers the question."}'
            )

        raise AssertionError(
            f"Unexpected generation call: {self.calls}"
        )

@pytest.mark.asyncio
async def test_sql_self_correction():

    generation_client = FakeGenerationClient()

    template_parser = SQLTemplateParser()

    controller = SQLController(
        generation_client=generation_client,
        sql_template_parser=template_parser,
    )

    result = await controller.query(
        provider="sqlite",
        database_url="sqlite:///assets/database/sql/ecommerce.db",
        question="Show the customer name of all customers.",
        max_rows=2,
        max_retries=2,
    )

    assert result["attempts"] == 2

    assert result["sql"] == (
        "SELECT name FROM customers\n"
        "LIMIT 2"
    )

    assert len(result["errors"]) == 1

    assert result["errors"][0]["attempt"] == 1

    assert result["errors"][0]["sql"] == (
        "SELECT customer_name FROM customers"
    )

    assert generation_client.calls == 3