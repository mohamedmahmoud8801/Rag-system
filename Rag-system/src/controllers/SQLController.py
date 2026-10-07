import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from models.SQLModel import SQLModel

from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLProviderFactory import SQLProviderFactory
from stores.sql.SQLValidator import (
    SQLValidator,
    SQLValidationError,
)

from stores.sql.templates import SQLTemplateParser

from stores.llm.LLMEnums import (
    OpenAIEnums,
    CoHereEnums,
    HuggingFaceEnums,
)


# ============================================================
# Logger
# ============================================================

logger = logging.getLogger("uvicorn.error")


class SQLController:

    # ========================================================
    # Semantic Verifier System Prompt
    # ========================================================

    semantic_system_prompt = """
You are a neutral SQL semantic verifier.

Evaluate ONLY the current:
- user question
- database schema
- generated SQL
- query result

Do not use unrelated examples.

Do not assume a specific table, column, field, or business
concept unless it appears in the CURRENT question and schema.

Do not generate a new SQL query.

Your job is semantic verification only.

Return ONLY valid JSON.
"""

    # ========================================================
    # SQL Correction System Prompt
    # ========================================================

    correction_system_prompt = """
You are a SQL correction engine.

Correct ONLY the current SQL using:
- current user question
- current schema
- current SQL
- current error

Do not use unrelated examples.

Return exactly one SELECT statement.
"""

    # ========================================================
    # Constructor
    # ========================================================

    def __init__(
        self,
        generation_client,
        sql_template_parser: SQLTemplateParser,
    ):
        self.generation_client = generation_client
        self.sql_template_parser = sql_template_parser
        self.sql_validator = SQLValidator()

    # ========================================================
    # Provider / Model
    # ========================================================

    async def _create_model(
        self,
        provider: str,
        database_url: str,
    ) -> SQLModel:

        provider_enum = SQLProviderEnum(
            provider.lower()
        )

        sql_provider = SQLProviderFactory.create(
            provider=provider_enum,
            database_url=database_url,
        )

        return await SQLModel.create_instance(
            provider=sql_provider,
        )

    # ========================================================
    # Schema
    # ========================================================

    async def get_schema(
        self,
        provider: str,
        database_url: str,
        tables: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        model = await self._create_model(
            provider=provider,
            database_url=database_url,
        )

        try:
            return await model.get_schema(
                tables=tables,
            )

        finally:
            model.provider.disconnect()

    # ========================================================
    # Enrich Schema With Sample Values
    # ========================================================

    async def _enrich_schema_with_sample_values(
        self,
        provider: str,
        database_url: str,
        schema: Dict[str, Any],
        max_values: int = 10,
        max_value_length: int = 80,
        max_avg_length: int = 40,
    ) -> Dict[str, Any]:

        logger.info(
            "[SQL DEBUG] STEP -> Enriching schema with categorical values"
        )

        model = await self._create_model(
            provider=provider,
            database_url=database_url,
        )

        try:

            enriched_schema: Dict[str, Any] = {}

            for table_name, table_info in schema.items():

                enriched_schema[table_name] = {
                    **table_info,
                    "columns": [],
                }

                for column in table_info.get(
                    "columns",
                    [],
                ):

                    enriched_column = {
                        **column,
                        "sample_values": [],
                    }

                    column_name = column["name"]

                    column_type = str(
                        column.get(
                            "type",
                            "",
                        )
                    ).upper()

                    is_text_column = any(
                        text_type in column_type
                        for text_type in (
                            "TEXT",
                            "VARCHAR",
                            "CHAR",
                            "STRING",
                        )
                    )

                    if not is_text_column:

                        enriched_schema[
                            table_name
                        ]["columns"].append(
                            enriched_column
                        )

                        continue

                    safe_table_name = (
                        self._quote_identifier(
                            table_name
                        )
                    )

                    safe_column_name = (
                        self._quote_identifier(
                            column_name
                        )
                    )

                    sample_query = (
                        f"SELECT DISTINCT "
                        f"{safe_column_name} "
                        f"FROM {safe_table_name} "
                        f"WHERE {safe_column_name} "
                        f"IS NOT NULL "
                        f"LIMIT {max_values}"
                    )

                    try:

                        logger.info(
                            "[SQL DEBUG] SAMPLE VALUES | "
                            "table=%s column=%s",
                            table_name,
                            column_name,
                        )

                        result = await model.execute(
                            query=sample_query
                        )

                        values = []

                        for row in result.get(
                            "rows",
                            [],
                        ):

                            value = row.get(
                                column_name
                            )

                            if value is None:
                                continue

                            value = str(
                                value
                            ).strip()

                            if not value:
                                continue

                            values.append(
                                value
                            )

                        if values:

                            lengths = [
                                len(value)
                                for value in values
                            ]

                            max_length = max(
                                lengths
                            )

                            avg_length = (
                                sum(lengths)
                                / len(lengths)
                            )

                            is_categorical = (
                                max_length
                                <= max_value_length
                                and avg_length
                                <= max_avg_length
                            )

                            if is_categorical:

                                enriched_column[
                                    "sample_values"
                                ] = values

                        logger.info(
                            "[SQL DEBUG] SAMPLE VALUES DONE | "
                            "table=%s column=%s values=%s",
                            table_name,
                            column_name,
                            enriched_column[
                                "sample_values"
                            ],
                        )

                    except Exception as exc:

                        logger.warning(
                            "[SQL DEBUG] SAMPLE VALUES FAILED | "
                            "table=%s column=%s error=%s",
                            table_name,
                            column_name,
                            exc,
                        )

                    enriched_schema[
                        table_name
                    ]["columns"].append(
                        enriched_column
                    )

            return enriched_schema

        finally:

            model.provider.disconnect()

            logger.info(
                "[SQL DEBUG] Sample-value provider disconnected"
            )

    # ========================================================
    # Tables
    # ========================================================

    async def get_tables(
        self,
        provider: str,
        database_url: str,
    ) -> List[str]:

        model = await self._create_model(
            provider=provider,
            database_url=database_url,
        )

        try:
            return await model.get_tables()

        finally:
            model.provider.disconnect()

    # ========================================================
    # Execute SQL Directly
    # ========================================================

    async def execute(
        self,
        provider: str,
        database_url: str,
        query: str,
        max_rows: int = 100,
    ) -> Dict[str, Any]:

        model = await self._create_model(
            provider=provider,
            database_url=database_url,
        )

        try:

            # ------------------------------------------------
            # STEP 1 - Get schema
            # ------------------------------------------------

            schema = await model.get_schema()

            if not schema:
                raise ValueError(
                    "No database schema was found."
                )

            # ------------------------------------------------
            # STEP 2 - Validate
            # ------------------------------------------------

            logger.info(
                "[SQL DEBUG] EXECUTE -> VALIDATING SQL"
            )

            validated_sql = (
                self.sql_validator.validate(
                    query=query,
                    schema=schema,
                    max_rows=max_rows,
                )
            )

            logger.info(
                "[SQL DEBUG] EXECUTE -> "
                "VALIDATED SQL = %s",
                validated_sql,
            )

            # ------------------------------------------------
            # STEP 3 - Execute
            # ------------------------------------------------

            logger.info(
                "[SQL DEBUG] EXECUTE -> EXECUTING SQL"
            )

            result = await model.execute(
                query=validated_sql
            )

            logger.info(
                "[SQL DEBUG] EXECUTE -> SUCCESS | rows=%d",
                result.get(
                    "row_count",
                    0,
                ),
            )

            return {
                "sql": validated_sql,
                "result": result,
                "columns": result.get(
                    "columns",
                    [],
                ),
                "rows": result.get(
                    "rows",
                    [],
                ),
                "row_count": result.get(
                    "row_count",
                    len(
                        result.get(
                            "rows",
                            [],
                        )
                    ),
                ),
            }

        finally:

            model.provider.disconnect()

            logger.info(
                "[SQL DEBUG] SQL provider disconnected"
            )

    # ========================================================
    # Generate SQL
    #
    # Generate only.
    #
    # Validation / execution / semantic verification /
    # retry are handled by query().
    # ========================================================

    async def generate_sql(
        self,
        provider: str,
        database_url: str,
        question: str,
        tables: Optional[List[str]] = None,
        max_rows: int = 100,
    ) -> Dict[str, Any]:

        total_start = time.perf_counter()

        logger.info(
            "[SQL DEBUG] generate_sql START | question=%s",
            question,
        )

        # ====================================================
        # STEP 1 - Get schema
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 1 -> get_schema()"
        )

        start = time.perf_counter()

        schema = await self.get_schema(
            provider=provider,
            database_url=database_url,
            tables=tables,
        )

        logger.info(
            "[SQL DEBUG] STEP 1 DONE | %.3fs | tables=%s",
            time.perf_counter() - start,
            list(schema.keys()),
        )

        if not schema:
            raise ValueError(
                "No database schema was found."
            )

        # ====================================================
        # STEP 1.1 - Enrich schema
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 1.1 -> "
            "_enrich_schema_with_sample_values()"
        )

        start = time.perf_counter()

        schema = (
            await self._enrich_schema_with_sample_values(
                provider=provider,
                database_url=database_url,
                schema=schema,
            )
        )

        logger.info(
            "[SQL DEBUG] STEP 1.1 DONE | %.3fs",
            time.perf_counter() - start,
        )

        # ====================================================
        # STEP 2 - Format schema
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 2 -> _format_schema()"
        )

        start = time.perf_counter()

        schema_text = self._format_schema(
            schema
        )

        logger.info(
            "[SQL DEBUG] STEP 2 DONE | %.3fs | chars=%d",
            time.perf_counter() - start,
            len(schema_text),
        )

        logger.info(
            "[SQL DEBUG] FORMATTED SCHEMA:\n%s",
            schema_text,
        )

        # ====================================================
        # STEP 3 - Load templates
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 3 -> SQL templates"
        )

        start = time.perf_counter()

        system_prompt = (
            self.sql_template_parser.get(
                "system_prompt"
            )
        )

        schema_prompt = (
            self.sql_template_parser.get(
                "schema_prompt",
                {
                    "schema": schema_text
                },
            )
        )

        footer_prompt = (
            self.sql_template_parser.get(
                "footer_prompt",
                {
                    "question": question
                },
            )
        )

        logger.info(
            "[SQL DEBUG] STEP 3 DONE | %.3fs",
            time.perf_counter() - start,
        )

        # ====================================================
        # STEP 4 - Build prompt
        # ====================================================

        full_prompt = "\n\n".join(
            [
                schema_prompt,
                footer_prompt,
            ]
        )

        logger.info(
            "[SQL DEBUG] STEP 4 DONE | prompt_chars=%d",
            len(full_prompt),
        )

        logger.info(
            "[SQL DEBUG] FULL PROMPT:\n%s",
            full_prompt,
        )

        # ====================================================
        # STEP 5 - Chat history
        # ====================================================

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        logger.info(
            "[SQL DEBUG] STEP 5 DONE"
        )

        # ====================================================
        # STEP 6 - LLM
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 6 -> CALLING LLM"
        )

        start = time.perf_counter()

        sql = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history,
            temperature=0.0,
            max_output_tokens=256,
        )

        logger.info(
            "[SQL DEBUG] STEP 6 DONE | %.3fs",
            time.perf_counter() - start,
        )

        if not sql:
            raise ValueError(
                "SQL generation returned an empty response."
            )

        # ====================================================
        # STEP 6.1 - Clean SQL
        # ====================================================

        sql = self._clean_sql(
            sql
        )

        logger.info(
            "[SQL DEBUG] GENERATED SQL = %s",
            sql,
        )

        # ====================================================
        # Total
        # ====================================================

        total_time = (
            time.perf_counter()
            - total_start
        )

        logger.info(
            "[SQL DEBUG] generate_sql END | total=%.3fs",
            total_time,
        )

        return {
            "question": question,
            "schema": schema,
            "sql": sql,
            "full_prompt": full_prompt,
            "chat_history": chat_history,
        }

    # ========================================================
    # SQL Self-Correction
    # ========================================================

    async def _generate_corrected_sql(
        self,
        question: str,
        schema: Dict[str, Any],
        previous_sql: str,
        error: str,
    ) -> str:

        logger.info(
            "[SQL DEBUG] Building self-correction prompt"
        )

        schema_text = self._format_schema(
            schema
        )

        correction_prompt = f"""
## Database Schema

{schema_text}

## Current User Question

{question}

## Previous SQL

{previous_sql}

## Error / Feedback

{error}

## Task

Correct the SQL query so that it semantically answers the
CURRENT user question and works with the CURRENT database
schema.

The previous SQL may be:

- syntactically invalid
- invalid against the schema
- executable but semantically incorrect

Use the feedback to identify the actual problem.

============================================================
SEMANTIC REASONING
============================================================

Before writing the corrected SQL, determine:

1. What does the user want returned?
2. Which table contains that information?
3. Which columns represent the requested output?
4. Which columns are conditions or filters?
5. Is aggregation required?
6. Is grouping required?
7. Is sorting required?
8. Is a calculation required?
9. Is text matching required?
10. Does the question request a specific ordering?

Do NOT import assumptions from unrelated examples.

Reason only from:

- CURRENT USER QUESTION
- CURRENT DATABASE SCHEMA
- PREVIOUS SQL
- CURRENT ERROR / FEEDBACK

============================================================
POLARITY / NEGATION
============================================================

Preserve the semantic polarity of EVERY condition.

For each condition:

1. Identify the target.
2. Identify the requested relation/operator.
3. Identify the value.
4. Determine whether the condition is positive or negative.
5. Generate SQL that preserves exactly that meaning.

Do NOT use substring matching to determine negation.

Examples:

"from Egypt"
    -> country = 'Egypt'

"not from Egypt"
    -> country != 'Egypt'

"contains phone"
    -> name LIKE '%phone%'

"does not contain phone"
    -> name NOT LIKE '%phone%'

"email exists"
    -> email IS NOT NULL

"email does not exist"
    -> email IS NULL

Arabic negation must also be preserved:

لا
ليس
ليست
ليسوا
غير
بدون
لا يوجد
لا تحتوي
غير موجود
غير صحيح
غير صحيحة
خاطئة

IMPORTANT:

"incorrect" is NOT "correct".

"غير صحيحة" is NOT "صحيحة".

The negation applies to the complete semantic condition,
not to individual substrings.

Apply this rule GENERICALLY to every column and every condition.
Do not hard-code any specific column or business concept.

============================================================
OUTPUT VS FILTER
============================================================

A column used in WHERE does NOT necessarily need to appear
in SELECT.

Example:

User:

"show questions whose type is multi_hop"

Correct:

SELECT question
FROM rag_evaluation
WHERE type = 'multi_hop'

============================================================
AGGREGATION
============================================================

If the user asks:

- how many
- count
- number of
- كم عدد
- total
- sum
- average
- avg
- percentage
- ratio
- نسبة

use the appropriate aggregate:

COUNT(...)
SUM(...)
AVG(...)
MIN(...)
MAX(...)

============================================================
GROUPING
============================================================

If the user asks:

"how many questions of each type?"

Correct structure:

SELECT type, COUNT(*)
FROM rag_evaluation
GROUP BY type

============================================================
SORTING
============================================================

If the user explicitly asks for ordering:

highest to lowest -> ORDER BY ... DESC
lowest to highest -> ORDER BY ... ASC

Do not add ordering if the user did not request it,
unless it is necessary for a deterministic top/ranking query.

============================================================
TEXT MATCHING
============================================================

starts with:
LIKE 'value%'

contains:
LIKE '%value%'

does not contain:
NOT LIKE '%value%'

Do NOT confuse starts-with with contains.

============================================================
NULL / EMPTY VALUES
============================================================

If the user asks for values that are not null:

IS NOT NULL

If the user asks for non-empty text:

IS NOT NULL AND column <> ''

============================================================
SAFETY
============================================================

Return exactly one SELECT query.

Never generate:

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
MERGE
REPLACE

Use only tables and columns present in the schema.

Do not invent columns.

Do not invent relationships.

Use JOIN only when supported by the schema.

Return only SQL.

Do not return Markdown.

Do not explain the SQL.

============================================================
FINAL REQUIREMENT
============================================================

The corrected SQL must answer the CURRENT user question,
not an example question.

Return only the corrected SQL.
"""

        logger.info(
            "[SQL DEBUG] SELF-CORRECTION PROMPT:\n%s",
            correction_prompt,
        )

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=self.correction_system_prompt,
                role=OpenAIEnums.SYSTEM.value,
            )
        ]

        logger.info(
            "[SQL DEBUG] SELF-CORRECTION -> CALLING LLM"
        )

        start = time.perf_counter()

        corrected_sql = self.generation_client.generate_text(
            prompt=correction_prompt,
            chat_history=chat_history,
            temperature=0.0,
            max_output_tokens=256,
        )

        logger.info(
            "[SQL DEBUG] SELF-CORRECTION DONE | %.3fs",
            time.perf_counter() - start,
        )

        if not corrected_sql:
            raise ValueError(
                "SQL correction returned an empty response."
            )

        corrected_sql = self._clean_sql(
            corrected_sql
        )

        logger.info(
            "[SQL DEBUG] CORRECTED SQL = %s",
            corrected_sql,
        )

        return corrected_sql

    # ========================================================
    # Query
    #
    # Generate
    #     ↓
    # Validate
    #     ↓
    # Execute
    #     ↓
    # Semantic Verify
    #     ↓
    # PASS -> return
    # FAIL -> contradiction check
    #             ↓
    #          contradiction -> return current SQL
    #             ↓
    #          correction -> retry
    # ========================================================

    async def query(
        self,
        provider: str,
        database_url: str,
        question: str,
        tables: Optional[List[str]] = None,
        max_rows: int = 100,
        max_retries: int = 2,
    ) -> Dict[str, Any]:

        total_start = time.perf_counter()

        logger.info(
            "[SQL DEBUG] query START | question=%s",
            question,
        )

        # ====================================================
        # STEP 1 - Generate
        # ====================================================

        logger.info(
            "[SQL DEBUG] STEP 1 -> generate_sql()"
        )

        start = time.perf_counter()

        generated = await self.generate_sql(
            provider=provider,
            database_url=database_url,
            question=question,
            tables=tables,
            max_rows=max_rows,
        )

        logger.info(
            "[SQL DEBUG] STEP 1 DONE | %.3fs",
            time.perf_counter() - start,
        )

        schema = generated["schema"]
        current_sql = generated["sql"]

        attempts = 0

        errors: List[Dict[str, Any]] = []

        # ====================================================
        # STEP 2 - Retry Loop
        # ====================================================

        while attempts <= max_retries:

            attempts += 1

            logger.info(
                "[SQL DEBUG] ATTEMPT %d/%d",
                attempts,
                max_retries + 1,
            )

            # =============================================
            # STEP 2.1 - SQL Validation
            # =============================================

            try:

                logger.info(
                    "[SQL DEBUG] VALIDATING SQL"
                )

                validated_sql = (
                    self.sql_validator.validate(
                        query=current_sql,
                        schema=schema,
                        max_rows=max_rows,
                    )
                )

                logger.info(
                    "[SQL DEBUG] VALIDATION SUCCESS | %s",
                    validated_sql,
                )

            except SQLValidationError as exc:

                error_message = str(exc)

                logger.warning(
                    "[SQL DEBUG] VALIDATION FAILED | %s",
                    error_message,
                )

                errors.append(
                    {
                        "attempt": attempts,
                        "stage": "validation",
                        "sql": current_sql,
                        "error": error_message,
                    }
                )

                if attempts > max_retries:

                    raise ValueError(
                        "SQL validation failed after "
                        f"{max_retries} retries. "
                        f"Last error: {error_message}"
                    )

                current_sql = (
                    await self._generate_corrected_sql(
                        question=question,
                        schema=schema,
                        previous_sql=current_sql,
                        error=error_message,
                    )
                )

                continue

            # =============================================
            # STEP 2.2 - Execute
            # =============================================

            try:

                logger.info(
                    "[SQL DEBUG] EXECUTING SQL"
                )

                execution_response = await self.execute(
                    provider=provider,
                    database_url=database_url,
                    query=validated_sql,
                    max_rows=max_rows,
                )

                if (
                    isinstance(
                        execution_response,
                        dict,
                    )
                    and "result" in execution_response
                    and isinstance(
                        execution_response["result"],
                        dict,
                    )
                ):

                    result = execution_response[
                        "result"
                    ]

                else:

                    result = execution_response

                logger.info(
                    "[SQL DEBUG] EXECUTION SUCCESS | rows=%d",
                    result.get(
                        "row_count",
                        len(
                            result.get(
                                "rows",
                                [],
                            )
                        ),
                    ),
                )

            except Exception as exc:

                error_message = str(exc)

                logger.warning(
                    "[SQL DEBUG] EXECUTION FAILED | %s",
                    error_message,
                )

                errors.append(
                    {
                        "attempt": attempts,
                        "stage": "execution",
                        "sql": validated_sql,
                        "error": error_message,
                    }
                )

                if attempts > max_retries:

                    raise ValueError(
                        "SQL execution failed after "
                        f"{max_retries} retries. "
                        f"Last error: {error_message}"
                    )

                current_sql = (
                    await self._generate_corrected_sql(
                        question=question,
                        schema=schema,
                        previous_sql=validated_sql,
                        error=error_message,
                    )
                )

                continue

            # =============================================
            # STEP 2.3 - Semantic Verification
            # =============================================

            try:

                logger.info(
                    "[SQL DEBUG] SEMANTIC VERIFICATION -> START"
                )

                semantic_check = (
                    await self._verify_sql_semantics(
                        question=question,
                        sql=validated_sql,
                        schema=schema,
                        result=result,
                    )
                )

                semantic_verdict = (
                    semantic_check.get(
                        "verdict",
                        "PASS",
                    )
                )

                logger.info(
                    "[SQL DEBUG] SEMANTIC VERDICT = %s",
                    semantic_verdict,
                )

            except Exception:

                logger.exception(
                    "[SQL DEBUG] SEMANTIC VERIFIER ERROR"
                )

                semantic_check = {
                    "verdict": "PASS",
                    "reason": (
                        "Semantic verifier failed internally."
                    ),
                    "verification_failed": True,
                }

                semantic_verdict = "PASS"

            # =============================================
            # STEP 2.4 - Semantic PASS
            # =============================================

            if semantic_verdict == "PASS":

                total_time = (
                    time.perf_counter()
                    - total_start
                )

                logger.info(
                    "[SQL DEBUG] query END | total=%.3fs",
                    total_time,
                )

                return {
                    "question": question,
                    "sql": validated_sql,
                    "result": result,
                    "schema": schema,
                    "attempts": attempts,
                    "errors": errors,
                }

            # =============================================
            # STEP 2.5 - Semantic Verifier Contradiction
            # =============================================

            if self._detect_verifier_contradiction(
                question=question,
                sql=validated_sql,
                semantic_check=semantic_check,
            ):

                logger.warning(
                    "[SQL DEBUG] SEMANTIC VERIFIER "
                    "CONTRADICTION DETECTED -> "
                    "IGNORING FALSE FAIL"
                )

                total_time = (
                    time.perf_counter()
                    - total_start
                )

                logger.info(
                    "[SQL DEBUG] query END | "
                    "semantic contradiction ignored | "
                    "total=%.3fs",
                    total_time,
                )

                return {
                    "question": question,
                    "sql": validated_sql,
                    "result": result,
                    "schema": schema,
                    "attempts": attempts,
                    "errors": errors,
                }

            # =============================================
            # STEP 2.6 - Semantic FAIL
            # =============================================

            reason = semantic_check.get(
                "reason",
                "Semantic SQL verification failed.",
            )

            correction_hint = (
                semantic_check.get(
                    "correction_hint",
                    "",
                )
            )

            error_message = (
                "Semantic SQL verification failed. "
                f"Reason: {reason}"
            )

            if correction_hint:

                error_message += (
                    " Correction hint: "
                    f"{correction_hint}"
                )

            logger.warning(
                "[SQL DEBUG] SEMANTIC VERIFICATION FAILED | %s",
                error_message,
            )

            errors.append(
                {
                    "attempt": attempts,
                    "stage": "semantic_validation",
                    "sql": validated_sql,
                    "error": error_message,
                }
            )

            if attempts > max_retries:

                total_time = (
                    time.perf_counter()
                    - total_start
                )

                logger.error(
                    "[SQL DEBUG] SEMANTIC RETRIES EXHAUSTED | "
                    "attempts=%d | total=%.3fs",
                    attempts,
                    total_time,
                )

                return {
                    "question": question,
                    "sql": validated_sql,
                    "result": result,
                    "schema": schema,
                    "attempts": attempts,
                    "errors": errors,
                }

            current_sql = (
                await self._generate_corrected_sql(
                    question=question,
                    schema=schema,
                    previous_sql=validated_sql,
                    error=error_message,
                )
            )

            logger.info(
                "[SQL DEBUG] "
                "SEMANTIC CORRECTION GENERATED | %s",
                current_sql,
            )

            continue

        # =================================================
        # Safety fallback
        # =================================================

        raise ValueError(
            "SQL query failed."
        )

    # ========================================================
    # Semantic SQL Verification
    # ========================================================

    async def _verify_sql_semantics(
        self,
        question: str,
        sql: str,
        schema: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION START"
        )

        schema_text = self._format_schema(
            schema
        )

        # ----------------------------------------------------
        # Result preview
        # ----------------------------------------------------

        result_preview = {
            "columns": result.get(
                "columns",
                [],
            ),
            "rows": result.get(
                "rows",
                [],
            )[:5],
            "row_count": result.get(
                "row_count",
                0,
            ),
        }

        # ----------------------------------------------------
        # Verification Prompt
        # ----------------------------------------------------

        verification_prompt = f"""
You are a semantic SQL verifier.

Your ONLY task is to determine whether the generated SQL
correctly answers the CURRENT user's question.

You are NOT generating SQL.
You are NOT rewriting SQL.

============================================================
CURRENT USER QUESTION
============================================================

{question}

============================================================
CURRENT DATABASE SCHEMA
============================================================

{schema_text}

============================================================
GENERATED SQL
============================================================

{sql}

============================================================
QUERY RESULT PREVIEW
============================================================

{json.dumps(
    result_preview,
    ensure_ascii=False,
    default=str,
)}

============================================================
CORE RULE
============================================================

Reason ONLY from:

1. CURRENT USER QUESTION
2. CURRENT DATABASE SCHEMA
3. GENERATED SQL
4. QUERY RESULT

Do NOT use unrelated examples.

Do NOT assume any specific table, column, field, or business
concept unless it appears in the CURRENT question and schema.

Every question must be analyzed independently.

============================================================
SEMANTIC ANALYSIS
============================================================

Determine:

1. Requested output.
2. Requested columns.
3. Requested conditions.
4. Requested operators.
5. Requested values.
6. Aggregation.
7. Grouping.
8. Sorting.
9. Text matching.
10. NULL handling.

============================================================
OUTPUT VS FILTER
============================================================

A column used in WHERE does NOT need to appear in SELECT.

============================================================
AGGREGATION
============================================================

If the user asks for:

- how many
- count
- number of
- كم عدد
- total
- sum
- average
- percentage
- ratio
- نسبة

verify that an appropriate aggregate is used.

============================================================
GROUPING
============================================================

If the user asks for grouped counts or grouped aggregates,
verify that GROUP BY is used when necessary.

============================================================
SORTING
============================================================

If the user explicitly requests ordering:

highest to lowest -> DESC

lowest to highest -> ASC

Do not require ORDER BY when ordering was not requested.

============================================================
TEXT MATCHING
============================================================

starts with:
LIKE 'value%'

contains:
LIKE '%value%'

does not contain:
NOT LIKE '%value%'

Do not confuse starts-with with contains.

============================================================
NULL
============================================================

exists:
IS NOT NULL

does not exist:
IS NULL

============================================================
ZERO ROWS
============================================================

Zero rows do NOT automatically mean the SQL is incorrect.

Judge the semantic structure of the SQL.

============================================================
NEGATION / POLARITY
============================================================

Evaluate every requested condition independently.

Do NOT determine polarity using substring matching.

For example:

"incorrect"

does NOT mean:

"correct"

Likewise:

"غير صحيحة"

does NOT mean:

"صحيحة"

Negation must be interpreted semantically as part of the
complete expression.

Common English negation:

not
no
without
does not
do not
isn't
aren't
never

Common Arabic negation:

لا
ليس
ليست
ليسوا
لم
لن
غير
بدون
لا يوجد
لا تحتوي
غير موجود
غير صحيح
غير صحيحة
خاطئة

============================================================
CONDITION EXTRACTION
============================================================

Extract the semantic conditions requested by the user.

For EACH condition return:

- target
- operator
- value
- polarity

Possible operators include:

=
!=
>
>=
<
<=
LIKE
NOT LIKE
IN
NOT IN
IS NULL
IS NOT NULL
EXISTS
NOT EXISTS

Polarity must be:

POSITIVE
NEGATIVE
NEUTRAL

IMPORTANT:

Do NOT hard-code any specific table, column, or business
concept.

Do NOT use substring matching.

============================================================
SQL CONDITION EXTRACTION
============================================================

Extract the conditions actually implemented by the SQL.

For EACH SQL condition return:

- target
- operator
- value
- polarity

Compare the semantic meaning of the user's conditions against
the SQL conditions.

============================================================
SEMANTIC CONDITION COMPARISON
============================================================

Before returning FAIL, compare:

USER CONDITION:

target + operator + value + polarity

against:

SQL CONDITION:

target + operator + value + polarity

If the conditions are semantically different, return FAIL.

If target, operator, value, and polarity are semantically
consistent, the condition is correct.

============================================================
FAIL EVIDENCE REQUIREMENT
============================================================

Return FAIL ONLY when there is a concrete semantic mismatch
in the generated SQL.

Do NOT claim a filter is missing if the SQL actually contains
the required filter.

Do NOT claim a requested column is missing if it appears in
SELECT.

Do NOT claim aggregation is missing if the SQL contains the
appropriate aggregate.

Do NOT claim GROUP BY is missing if it is actually present and
appropriate.

Do NOT infer a semantic failure only from result rows.

If the claimed problem is contradicted by the actual SQL,
return PASS.

============================================================
FINAL DECISION
============================================================

PASS if the SQL correctly implements the CURRENT question.

FAIL if there is a meaningful semantic mismatch.

Do NOT fail merely because:

- a filter column is not selected
- the query returns zero rows
- an aggregate query does not return normal entity rows
- GROUP BY is used appropriately
- the SQL uses a valid equivalent expression
- the SQL differs syntactically from another valid solution

Focus on semantic meaning.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

For PASS:

{{
    "verdict": "PASS",
    "reason": "Brief explanation.",
    "correction_hint": "",
    "requested_conditions": [
        {{
            "target": "...",
            "operator": "...",
            "value": "...",
            "polarity": "POSITIVE"
        }}
    ],
    "sql_conditions": [
        {{
            "target": "...",
            "operator": "...",
            "value": "...",
            "polarity": "POSITIVE"
        }}
    ]
}}

For FAIL:

{{
    "verdict": "FAIL",
    "reason": "Brief explanation of the actual semantic mismatch.",
    "correction_hint": "Specific correction needed.",
    "requested_conditions": [
        {{
            "target": "...",
            "operator": "...",
            "value": "...",
            "polarity": "POSITIVE"
        }}
    ],
    "sql_conditions": [
        {{
            "target": "...",
            "operator": "...",
            "value": "...",
            "polarity": "NEGATIVE"
        }}
    ]
}}

Rules:

- requested_conditions = conditions requested by the user.
- sql_conditions = conditions implemented by the SQL.
- Include one object per relevant condition.
- Use [] when there are no filter conditions.
- target must be concise.
- operator must represent semantic meaning.
- value must represent the actual requested/implemented value.
- polarity must be POSITIVE, NEGATIVE, or NEUTRAL.
- Do not include chain-of-thought.
- Do not include explanations outside JSON.
"""

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION PROMPT:\n%s",
            verification_prompt,
        )

        # ----------------------------------------------------
        # Chat history
        # ----------------------------------------------------

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=self.semantic_system_prompt,
                role=OpenAIEnums.SYSTEM.value,
            )
        ]

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION -> CALLING LLM"
        )

        start = time.perf_counter()

        verification_response = (
             self.generation_client.generate_text(
                prompt=verification_prompt,
                chat_history=chat_history,
                temperature=0.0,
                max_output_tokens=512,
            )
        )

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION DONE | %.3fs",
            time.perf_counter() - start,
        )

        if not verification_response:

            logger.warning(
                "[SQL DEBUG] SEMANTIC VERIFICATION "
                "RETURNED EMPTY RESPONSE"
            )

            return {
                "verdict": "PASS",
                "reason": (
                    "Semantic verifier returned "
                    "an empty response."
                ),
                "verification_failed": True,
            }

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION RAW RESPONSE:\n%s",
            verification_response,
        )

        verification = (
            self._parse_semantic_verification(
                verification_response
            )
        )

        logger.info(
            "[SQL DEBUG] SEMANTIC VERIFICATION RESULT: %s",
            verification,
        )

        return verification

    # ========================================================
    # Semantic Verifier Contradiction Detection
    # ========================================================

    @staticmethod
    def _detect_verifier_contradiction(
        question: str,
        sql: str,
        semantic_check: Dict[str, Any],
    ) -> bool:

        reason = str(
            semantic_check.get(
                "reason",
                "",
            )
        )

        correction_hint = str(
            semantic_check.get(
                "correction_hint",
                "",
            )
        )

        feedback = (
            f"{reason} {correction_hint}"
        ).lower()

        normalized_sql = re.sub(
            r"\s+",
            " ",
            sql.strip().lower(),
        )

        # ========================================================
        # 1. FILTER CONTRADICTION
        # ========================================================

        no_filter_patterns = [
            r"no where",
            r"without where",
            r"no filtering",
            r"without(?:\s+any)?\s+filtering",
            r"missing filter",
            r"missing a filter",
            r"missing filtering",
            r"missing a filtering",
            r"does not filter",
            r"doesn't filter",
            r"no filter",
            r"without(?:\s+any)?\s+filter",
            r"filter is missing",
            r"filtering is missing",
        ]

        says_filter_missing = any(
            re.search(
                pattern,
                feedback,
                re.IGNORECASE,
            )
            for pattern in no_filter_patterns
        )

        has_where = bool(
            re.search(
                r"\bwhere\b",
                normalized_sql,
                re.IGNORECASE,
            )
        )

        if says_filter_missing and has_where:

            logger.warning(
                "[SQL DEBUG] SEMANTIC VERIFIER CONTRADICTION | "
                "Verifier claims missing filter, "
                "but SQL contains WHERE"
            )

            return True

        # ========================================================
        # 2. REQUESTED COLUMN CONTRADICTION
        # ========================================================

        missing_column_patterns = [
            r"missing column [`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"does not include column [`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"does not select column [`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"missing [`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`'\"]? column",
        ]

        for pattern in missing_column_patterns:

            match = re.search(
                pattern,
                feedback,
                re.IGNORECASE,
            )

            if not match:
                continue

            missing_column = (
                match.group(1).lower()
            )

            select_match = re.search(
                r"\bselect\b(.*?)\bfrom\b",
                normalized_sql,
                re.IGNORECASE | re.DOTALL,
            )

            if not select_match:
                continue

            select_part = (
                select_match.group(1)
            )

            if re.search(
                rf"\b{re.escape(missing_column)}\b",
                select_part,
                re.IGNORECASE,
            ):

                logger.warning(
                    "[SQL DEBUG] SEMANTIC VERIFIER CONTRADICTION | "
                    "Verifier claims missing column '%s', "
                    "but SQL selects it",
                    missing_column,
                )

                return True

        # ========================================================
        # 3. STRUCTURED CONDITION CONTRADICTION
        # ========================================================

        requested_conditions = (
            semantic_check.get(
                "requested_conditions",
                [],
            )
        )

        sql_conditions = (
            semantic_check.get(
                "sql_conditions",
                [],
            )
        )

        if not isinstance(
            requested_conditions,
            list,
        ):
            requested_conditions = []

        if not isinstance(
            sql_conditions,
            list,
        ):
            sql_conditions = []

        def normalize_condition(
            condition: Any,
        ) -> Optional[Dict[str, str]]:

            if not isinstance(
                condition,
                dict,
            ):
                return None

            target = str(
                condition.get(
                    "target",
                    "",
                )
            ).strip().lower()

            operator = str(
                condition.get(
                    "operator",
                    "",
                )
            ).strip().upper()

            value = str(
                condition.get(
                    "value",
                    "",
                )
            ).strip().lower()

            polarity = str(
                condition.get(
                    "polarity",
                    "",
                )
            ).strip().upper()

            target = re.sub(
                r"\s+",
                " ",
                target,
            )

            operator = re.sub(
                r"\s+",
                " ",
                operator,
            )

            value = re.sub(
                r"\s+",
                " ",
                value,
            )

            value = value.strip(
                "'\"`"
            )

            return {
                "target": target,
                "operator": operator,
                "value": value,
                "polarity": polarity,
            }

        normalized_requested = [
            normalize_condition(
                condition
            )
            for condition in requested_conditions
        ]

        normalized_sql_conditions = [
            normalize_condition(
                condition
            )
            for condition in sql_conditions
        ]

        normalized_requested = [
            condition
            for condition in normalized_requested
            if condition is not None
        ]

        normalized_sql_conditions = [
            condition
            for condition in normalized_sql_conditions
            if condition is not None
        ]

        def condition_matches(
            requested: Dict[str, str],
            actual: Dict[str, str],
        ) -> bool:

            if (
                requested["target"]
                and actual["target"]
                and requested["target"]
                != actual["target"]
            ):
                return False

            if (
                requested["operator"]
                and actual["operator"]
                and requested["operator"]
                != actual["operator"]
            ):
                return False

            if (
                requested["value"]
                and actual["value"]
                and requested["value"]
                != actual["value"]
            ):
                return False

            if (
                requested["polarity"]
                and actual["polarity"]
                and requested["polarity"]
                != actual["polarity"]
            ):
                return False

            return True

        if (
            normalized_requested
            and normalized_sql_conditions
        ):

            all_requested_conditions_match = all(
                any(
                    condition_matches(
                        requested,
                        actual,
                    )
                    for actual
                    in normalized_sql_conditions
                )
                for requested
                in normalized_requested
            )

            if all_requested_conditions_match:

                logger.warning(
                    "[SQL DEBUG] SEMANTIC VERIFIER CONTRADICTION | "
                    "Verifier returned FAIL, but "
                    "requested_conditions and sql_conditions "
                    "are semantically consistent."
                )

                return True

        return False

    # ========================================================
    # Parse Semantic Verification
    # ========================================================

    @staticmethod
    def _parse_semantic_verification(
        response: str,
    ) -> Dict[str, Any]:

        response = response.strip()

        # ----------------------------------------------------
        # Remove <think>...</think>
        # ----------------------------------------------------

        response = re.sub(
            r"<think>.*?</think>",
            "",
            response,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        # ----------------------------------------------------
        # Remove markdown fences
        # ----------------------------------------------------

        if response.startswith(
            "```json"
        ):

            response = response[7:]

        elif response.startswith(
            "```"
        ):

            response = response[3:]

        if response.endswith(
            "```"
        ):

            response = response[:-3]

        response = response.strip()

        # ----------------------------------------------------
        # Direct JSON parse
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                response
            )

            if isinstance(
                parsed,
                dict,
            ):

                verdict = str(
                    parsed.get(
                        "verdict",
                        "",
                    )
                ).upper()

                if verdict in {
                    "PASS",
                    "FAIL",
                }:

                    parsed["verdict"] = verdict

                    return parsed

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # Extract JSON object from surrounding text
        # ----------------------------------------------------

        decoder = json.JSONDecoder()

        for index, char in enumerate(
            response
        ):

            if char != "{":
                continue

            try:

                parsed, _ = decoder.raw_decode(
                    response[index:]
                )

                if not isinstance(
                    parsed,
                    dict,
                ):
                    continue

                verdict = str(
                    parsed.get(
                        "verdict",
                        "",
                    )
                ).upper()

                if verdict in {
                    "PASS",
                    "FAIL",
                }:

                    parsed["verdict"] = verdict

                    return parsed

            except json.JSONDecodeError:
                continue

        # ----------------------------------------------------
        # Fail-open if verifier output is malformed
        # ----------------------------------------------------

        logger.warning(
            "[SQL DEBUG] Could not parse semantic "
            "verification response: %s",
            response,
        )

        return {
            "verdict": "PASS",
            "reason": (
                "Semantic verifier response "
                "could not be parsed."
            ),
            "verification_failed": True,
        }

    # ========================================================
    # Format Schema
    # ========================================================

    @staticmethod
    def _format_schema(
        schema: Dict[str, Any],
    ) -> str:

        schema_parts: List[str] = []

        for table_name, table_info in schema.items():

            schema_parts.append(
                f"Table: {table_name}"
            )

            schema_parts.append(
                "Columns:"
            )

            for column in table_info.get(
                "columns",
                [],
            ):

                column_line = (
                    f"- Column: {column['name']} "
                    f"| Type: {column['type']}"
                )

                if column.get(
                    "primary_key",
                    False,
                ):

                    column_line += (
                        " | PRIMARY KEY"
                    )

                if not column.get(
                    "nullable",
                    True,
                ):

                    column_line += (
                        " | NOT NULL"
                    )

                sample_values = column.get(
                    "sample_values",
                    [],
                )

                if sample_values:

                    formatted_values = ", ".join(
                        repr(value)
                        for value in sample_values
                    )

                    column_line += (
                        f" | examples: "
                        f"{formatted_values}"
                    )

                schema_parts.append(
                    column_line
                )

            foreign_keys = table_info.get(
                "foreign_keys",
                [],
            )

            if foreign_keys:

                schema_parts.append(
                    "Foreign Keys:"
                )

                for foreign_key in foreign_keys:

                    column = str(
                        foreign_key.get(
                            "column",
                            "",
                        )
                    ).strip()

                    references = foreign_key.get(
                        "references"
                    )

                    if references:

                        reference_text = str(
                            references
                        ).strip()

                    else:

                        references_table = str(
                            foreign_key.get(
                                "references_table",
                                "",
                            )
                        ).strip()

                        references_column = str(
                            foreign_key.get(
                                "references_column",
                                "",
                            )
                        ).strip()

                        if (
                            references_table
                            and references_column
                        ):

                            reference_text = (
                                f"{references_table}."
                                f"{references_column}"
                            )

                        elif references_table:

                            reference_text = (
                                references_table
                            )

                        else:

                            reference_text = (
                                references_column
                            )

                    if (
                        column
                        and reference_text
                    ):

                        schema_parts.append(
                            f"- {column} "
                            f"REFERENCES "
                            f"{reference_text}"
                        )

            schema_parts.append("")

        return "\n".join(
            schema_parts
        )

    # ========================================================
    # Quote SQL Identifier
    # ========================================================

    @staticmethod
    def _quote_identifier(
        identifier: str,
    ) -> str:

        escaped_identifier = identifier.replace(
            '"',
            '""',
        )

        return f'"{escaped_identifier}"'

    # ========================================================
    # Clean SQL
    # ========================================================

    @staticmethod
    def _clean_sql(
        sql: str,
    ) -> str:

        sql = sql.strip()

        if sql.startswith(
            "```sql"
        ):

            sql = sql[6:]

        elif sql.startswith(
            "```"
        ):

            sql = sql[3:]

        if sql.endswith(
            "```"
        ):

            sql = sql[:-3]

        return sql.strip()