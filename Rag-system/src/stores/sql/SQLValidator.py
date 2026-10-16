import re
from typing import Any, Dict, List, Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.qualify import qualify


class SQLValidationError(ValueError):
    pass


class SQLValidator:
    """
    Validates SQL produced by the LLM using a real SQL parser (sqlglot)
    instead of regular expressions.

    validate() returns the SQL to execute: a single read-only statement
    whose tables, columns and functions were checked and whose row count
    is capped at max_rows. It raises SQLValidationError with a message
    meant to be fed back to the LLM for correction.
    """

    MAX_QUERY_LENGTH = 8000

    DIALECTS = {
        "sqlite": "sqlite",
        "postgresql": "postgres",
        "postgres": "postgres",
    }

    # Any of these anywhere in the statement (even nested in a CTE).
    FORBIDDEN_NODES = (
        "Insert", "Update", "Delete", "Drop", "Alter", "AlterTable",
        "Create", "Command", "Merge", "TruncateTable", "Pragma", "Set",
        "Use", "Attach", "Detach", "Copy", "Transaction", "Commit",
        "Rollback", "LoadData", "Into", "Lock", "Analyze", "Describe",
        "Show", "Kill", "Grant", "Revoke",
    )

    # Known sqlglot functions that can be abused (resource exhaustion /
    # reading files).
    BLOCKED_FUNCTION_NODES = ("GenerateSeries", "ReadCSV", "Sleep")

    # Functions sqlglot does not model itself ("anonymous") are only
    # accepted if listed here. This blocks pg_sleep, pg_read_file,
    # load_extension, lo_import, readfile, ...
    ALLOWED_ANONYMOUS_FUNCTIONS = {
        # strings
        "lower", "upper", "trim", "ltrim", "rtrim", "length", "char_length",
        "substr", "substring", "replace", "instr", "position", "strpos",
        "concat", "concat_ws", "left", "right", "lpad", "rpad", "reverse",
        "initcap", "split_part", "printf", "format", "regexp_replace",
        "regexp_like", "translate", "unicode", "hex",
        # numbers
        "abs", "round", "ceil", "ceiling", "floor", "sqrt", "power", "pow",
        "mod", "sign", "exp", "ln", "log", "log10", "trunc", "random",
        # null handling / conditionals
        "coalesce", "ifnull", "nullif", "iif", "greatest", "least",
        # aggregates / windows
        "count", "sum", "avg", "min", "max", "total", "group_concat",
        "string_agg", "row_number", "rank", "dense_rank", "ntile", "lag",
        "lead", "first_value", "last_value", "nth_value", "percent_rank",
        "cume_dist", "median", "stddev", "variance",
        # dates
        "date", "time", "datetime", "julianday", "strftime", "unixepoch",
        "now", "current_date", "current_time", "current_timestamp",
        "date_trunc", "date_part", "to_char", "to_date", "age", "extract",
        "date_diff", "datediff", "dateadd",
        # misc
        "typeof", "cast", "json_extract", "json_object", "json_array",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        query: str,
        schema: Dict[str, Any],
        max_rows: int = 100,
        dialect: Optional[str] = None,
    ) -> str:

        dialect = self.DIALECTS.get((dialect or "").lower())

        sql = self._clean_query(query)

        root = self._parse(sql, dialect)

        self._validate_root_is_select(root)
        self._validate_forbidden_nodes(root)
        self._validate_no_recursion(root)
        self._validate_functions(root)
        self._validate_joins(root)
        self._validate_tables(root, schema)
        self._validate_columns(root, schema, dialect)

        root = self._apply_limit(root, max_rows)

        return root.sql(dialect=dialect, comments=False)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _clean_query(self, query: str) -> str:

        if not query or not str(query).strip():
            raise SQLValidationError("SQL query is empty.")

        sql = str(query).strip()

        if sql.startswith("```"):
            sql = re.sub(r"^```[a-zA-Z]*", "", sql).strip()
            sql = sql.removesuffix("```").strip()

        if len(sql) > self.MAX_QUERY_LENGTH:
            raise SQLValidationError(
                f"SQL query is too long (max {self.MAX_QUERY_LENGTH} characters)."
            )

        return sql

    def _parse(self, sql: str, dialect: Optional[str]) -> exp.Expression:

        try:
            statements = sqlglot.parse(sql, read=dialect)
        except SqlglotError as exc:
            raise SQLValidationError(
                f"Invalid SQL syntax: {str(exc).splitlines()[0]}"
            )

        statements = [s for s in statements if s is not None]

        if not statements:
            raise SQLValidationError("SQL query is empty.")

        if len(statements) > 1:
            raise SQLValidationError(
                "Only a single SQL statement is allowed."
            )

        root = statements[0]

        # (SELECT ...) -> SELECT ...
        while isinstance(root, exp.Subquery) and not root.args.get("alias"):
            root = root.this

        return root

    # ------------------------------------------------------------------
    # Structural checks
    # ------------------------------------------------------------------

    @staticmethod
    def _node_classes(names) -> tuple:
        return tuple(
            getattr(exp, name) for name in names if hasattr(exp, name)
        )

    def _validate_root_is_select(self, root: exp.Expression) -> None:

        allowed = (exp.Select,) + self._node_classes(
            ("SetOperation", "Union", "Intersect", "Except")
        )

        if not isinstance(root, allowed):
            raise SQLValidationError(
                "Only SELECT queries are allowed."
            )

    def _validate_forbidden_nodes(self, root: exp.Expression) -> None:

        forbidden = self._node_classes(self.FORBIDDEN_NODES)

        found = root.find(*forbidden)

        if found is not None:
            raise SQLValidationError(
                f"Forbidden SQL operation: {type(found).__name__.upper()}."
            )

        if root.args.get("fetch"):
            raise SQLValidationError(
                "Use LIMIT instead of FETCH FIRST."
            )

    @staticmethod
    def _validate_no_recursion(root: exp.Expression) -> None:

        for with_node in root.find_all(exp.With):
            if with_node.args.get("recursive"):
                raise SQLValidationError(
                    "Recursive queries (WITH RECURSIVE) are not allowed."
                )

    def _validate_functions(self, root: exp.Expression) -> None:

        blocked = self._node_classes(self.BLOCKED_FUNCTION_NODES)

        for node in root.find_all(exp.Func):

            if blocked and isinstance(node, blocked):
                raise SQLValidationError(
                    f"Function is not allowed: {type(node).__name__}."
                )

            if type(node).__name__.startswith("Anonymous"):

                name = str(node.name or "").lower()

                if name not in self.ALLOWED_ANONYMOUS_FUNCTIONS:
                    raise SQLValidationError(
                        f"Function is not allowed: {name}."
                    )

    @staticmethod
    def _validate_joins(root: exp.Expression) -> None:

        for join in root.find_all(exp.Join):

            has_condition = bool(
                join.args.get("on") or join.args.get("using")
            )

            is_natural = str(join.args.get("method") or "").upper() == "NATURAL"

            if not has_condition and not is_natural:
                raise SQLValidationError(
                    "Every JOIN needs an ON or USING condition. "
                    "Cartesian products and comma joins are not allowed."
                )

    # ------------------------------------------------------------------
    # Tables / columns
    # ------------------------------------------------------------------

    @staticmethod
    def _schema_columns(schema: Dict[str, Any]) -> Dict[str, List[str]]:

        return {
            table: [
                column["name"]
                for column in (info or {}).get("columns", [])
            ]
            for table, info in schema.items()
        }

    def _validate_tables(
        self,
        root: exp.Expression,
        schema: Dict[str, Any],
    ) -> None:

        known = {name.lower() for name in schema}

        cte_names = {
            cte.alias_or_name.lower()
            for cte in root.find_all(exp.CTE)
        }

        for table in root.find_all(exp.Table):

            if not isinstance(table.this, exp.Identifier):
                # table-valued function, already handled elsewhere
                continue

            name = table.name.lower()

            if not table.db and name in cte_names:
                continue

            if table.db and table.db.lower() not in ("main", "public"):
                raise SQLValidationError(
                    f"Schema-qualified table is not allowed: {table.db}.{table.name}."
                )

            if name not in known:
                raise SQLValidationError(
                    f"Unknown table: {table.name}. "
                    f"Available tables: {', '.join(schema) or 'none'}."
                )

    def _validate_columns(
        self,
        root: exp.Expression,
        schema: Dict[str, Any],
        dialect: Optional[str],
    ) -> None:

        columns = self._schema_columns(schema)

        mapping = {
            table: {name: "TEXT" for name in names}
            for table, names in columns.items()
        }

        try:
            qualify(
                root.copy(),
                schema=mapping,
                dialect=dialect,
                validate_qualify_columns=True,
                identify=False,
            )

        except OptimizeError as exc:

            used = {
                t.name.lower() for t in root.find_all(exp.Table)
            }

            hint = "; ".join(
                f"{table}({', '.join(names)})"
                for table, names in columns.items()
                if table.lower() in used
            )

            raise SQLValidationError(
                f"{str(exc).splitlines()[0]}."
                + (f" Available columns: {hint}." if hint else "")
            )

        except SqlglotError as exc:
            raise SQLValidationError(
                f"Could not validate the query: {str(exc).splitlines()[0]}"
            )

    # ------------------------------------------------------------------
    # Row limit
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_limit(root: exp.Expression, max_rows: int) -> exp.Expression:

        limit = root.args.get("limit")

        if limit is None:
            return root.limit(max_rows)

        value = limit.args.get("expression")

        if (
            isinstance(value, exp.Literal)
            and value.is_int
            and int(value.name) <= max_rows
        ):
            return root

        return root.limit(max_rows)