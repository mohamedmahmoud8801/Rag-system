import re
from typing import Any, Dict, List, Tuple


class SQLValidationError(ValueError):
    """Raised when generated SQL fails validation."""


class SQLValidator:

    FORBIDDEN_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
    }

    SQL_KEYWORDS = {
        "ON",
        "WHERE",
        "JOIN",
        "INNER",
        "LEFT",
        "RIGHT",
        "FULL",
        "OUTER",
        "CROSS",
        "GROUP",
        "ORDER",
        "LIMIT",
        "HAVING",
        "UNION",
        "OFFSET",
    }

    # ============================================================
    # Main Validation Pipeline
    # ============================================================

    def validate(
        self,
        query: str,
        schema: Dict[str, Any],
        max_rows: int = 100,
    ) -> str:

        if not query or not query.strip():
            raise SQLValidationError(
                "Generated SQL is empty."
            )

        query = self._clean_query(query)

        # --------------------------------------------------------
        # 1. Single statement
        # --------------------------------------------------------

        self._validate_single_statement(query)

        # --------------------------------------------------------
        # 2. SELECT only
        # --------------------------------------------------------

        self._validate_select_only(query)

        # --------------------------------------------------------
        # 3. Forbidden operations
        # --------------------------------------------------------

        self._validate_forbidden_keywords(query)

        # --------------------------------------------------------
        # 4. Extract tables and aliases
        # --------------------------------------------------------

        tables = self._extract_tables(query)

        # --------------------------------------------------------
        # 5. Validate tables
        # --------------------------------------------------------

        self._validate_tables(
            tables=tables,
            schema=schema,
        )

        # --------------------------------------------------------
        # 6. Extract and validate columns
        # --------------------------------------------------------

        columns = self._extract_columns(query)

        self._validate_columns(
            columns=columns,
            tables=tables,
            schema=schema,
        )

        # --------------------------------------------------------
        # 7. Validate JOIN relationships
        # --------------------------------------------------------

        self._validate_join_relationships(
            query=query,
            tables=tables,
            schema=schema,
        )

        # --------------------------------------------------------
        # 8. Apply LIMIT
        # --------------------------------------------------------

        query = self._apply_limit(
            query=query,
            max_rows=max_rows,
        )

        return query

    # ============================================================
    # Clean Query
    # ============================================================

    @staticmethod
    def _clean_query(
        query: str,
    ) -> str:

        query = query.strip()

        if query.startswith("```sql"):
            query = query[6:]

        elif query.startswith("```"):
            query = query[3:]

        if query.endswith("```"):
            query = query[:-3]

        return query.strip().rstrip(";").strip()

    # ============================================================
    # Single Statement
    # ============================================================

    @staticmethod
    def _validate_single_statement(
        query: str,
    ) -> None:

        if ";" in query:
            raise SQLValidationError(
                "Multiple SQL statements are not allowed."
            )

    # ============================================================
    # SELECT Only
    # ============================================================

    @classmethod
    def _validate_select_only(
        cls,
        query: str,
    ) -> None:

        normalized = query.strip().upper()

        if not normalized.startswith("SELECT"):
            raise SQLValidationError(
                "Only SELECT queries are allowed."
            )

    # ============================================================
    # Forbidden Keywords
    # ============================================================

    @classmethod
    def _validate_forbidden_keywords(
        cls,
        query: str,
    ) -> None:

        normalized = query.upper()

        for keyword in cls.FORBIDDEN_KEYWORDS:

            pattern = rf"\b{re.escape(keyword)}\b"

            if re.search(
                pattern,
                normalized,
            ):
                raise SQLValidationError(
                    f"Forbidden SQL operation detected: {keyword}"
                )

    # ============================================================
    # Extract Tables and Aliases
    # ============================================================

    @classmethod
    def _extract_tables(
        cls,
        query: str,
    ) -> Dict[str, str]:

        """
        Extract tables and aliases from FROM / JOIN clauses.

        Examples:

            FROM customers

        becomes:

            {
                "customers": "customers"
            }

        --------------------------------------------------------

            FROM customers c

        becomes:

            {
                "customers": "customers",
                "c": "customers"
            }

        --------------------------------------------------------

            FROM customers AS c

        becomes:

            {
                "customers": "customers",
                "c": "customers"
            }
        """

        tables: Dict[str, str] = {}

        # --------------------------------------------------------
        # Match FROM / JOIN + table name
        # --------------------------------------------------------

        table_pattern = re.compile(
            r"""
            \b
            (?:FROM|JOIN)
            \s+
            (?P<table>
                [A-Za-z_][A-Za-z0-9_]*
            )
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        matches = list(
            table_pattern.finditer(query)
        )

        for index, match in enumerate(matches):

            table_name = match.group("table")

            # Always register actual table
            tables[table_name] = table_name

            # ----------------------------------------------------
            # Determine where this table declaration ends
            # ----------------------------------------------------

            current_end = match.end()

            if index + 1 < len(matches):

                next_start = matches[index + 1].start()

                declaration = query[
                    current_end:next_start
                ]

            else:

                declaration = query[
                    current_end:
                ]

            # ----------------------------------------------------
            # Remove ON / WHERE / GROUP / ORDER etc.
            # ----------------------------------------------------

            stop_pattern = re.compile(
                r"""
                \b
                (?:
                    ON
                    |WHERE
                    |GROUP
                    |ORDER
                    |HAVING
                    |LIMIT
                    |OFFSET
                    |UNION
                )
                \b
                """,
                re.IGNORECASE | re.VERBOSE,
            )

            stop_match = stop_pattern.search(
                declaration
            )

            if stop_match:

                declaration = declaration[
                    :stop_match.start()
                ]

            # ----------------------------------------------------
            # Check AS alias
            # ----------------------------------------------------

            as_match = re.match(
                r"""
                \s+
                AS
                \s+
                (?P<alias>
                    [A-Za-z_][A-Za-z0-9_]*
                )
                """,
                declaration,
                re.IGNORECASE | re.VERBOSE,
            )

            if as_match:

                alias = as_match.group("alias")

                if alias.upper() not in cls.SQL_KEYWORDS:

                    tables[alias] = table_name

                continue

            # ----------------------------------------------------
            # Check implicit alias
            # ----------------------------------------------------

            implicit_match = re.match(
                r"""
                \s+
                (?P<alias>
                    [A-Za-z_][A-Za-z0-9_]*
                )
                """,
                declaration,
                re.IGNORECASE | re.VERBOSE,
            )

            if implicit_match:

                alias = implicit_match.group("alias")

                if alias.upper() not in cls.SQL_KEYWORDS:

                    tables[alias] = table_name

        return tables

    # ============================================================
    # Validate Tables
    # ============================================================

    @staticmethod
    def _validate_tables(
        tables: Dict[str, str],
        schema: Dict[str, Any],
    ) -> None:

        available_tables = set(
            schema.keys()
        )

        for alias, table_name in tables.items():

            if table_name not in available_tables:

                raise SQLValidationError(
                    f"Unknown table: {table_name}"
                )

    # ============================================================
    # Extract Qualified Columns
    # ============================================================

        # ============================================================
    # Extract Columns
    # ============================================================


    @staticmethod
    def _extract_columns(
        query: str,
    ) -> List[str]:
        """
        Extract column references from SQL.

        Supports:
            SELECT name FROM customers

        and:
            SELECT c.name
            FROM customers c

        Qualified columns are returned as:
            c.name

        Unqualified columns are returned as:
            name

        SELECT aliases are ignored.

        Example:
            SELECT AVG(score) AS avg_score
            FROM results

        Extracted column:
            score

        Ignored:
            avg_score
        """

        columns: List[str] = []

        # --------------------------------------------------------
        # Remove SQL string literals
        #
        # Example:
        #
        # WHERE name = 'customer_name'
        #
        # We do not want "customer_name" to be treated
        # as a column.
        # --------------------------------------------------------

        query_without_strings = re.sub(
            r"'(?:''|[^'])*'",
            "",
            query,
        )

        # --------------------------------------------------------
        # Qualified columns
        #
        # c.name
        # customers.name
        # --------------------------------------------------------

        qualified_matches = re.findall(
            r"""
            \b
            (
                [A-Za-z_][A-Za-z0-9_]*
            )
            \.
            (
                [A-Za-z_][A-Za-z0-9_]*
            )
            \b
            """,
            query_without_strings,
            re.IGNORECASE | re.VERBOSE,
        )

        for alias, column in qualified_matches:
            columns.append(
                f"{alias}.{column}"
            )

        # --------------------------------------------------------
        # Remove qualified references from the query
        #
        # Otherwise "c.name" would also produce "name".
        # --------------------------------------------------------

        query_without_qualified = re.sub(
            r"""
            \b
            [A-Za-z_][A-Za-z0-9_]*
            \.
            [A-Za-z_][A-Za-z0-9_]*
            \b
            """,
            "",
            query_without_strings,
            flags=re.IGNORECASE | re.VERBOSE,
        )

        # --------------------------------------------------------
        # SQL keywords / clauses that are NOT columns
        # --------------------------------------------------------

        ignored_keywords = {
            "SELECT",
            "FROM",
            "JOIN",
            "INNER",
            "LEFT",
            "RIGHT",
            "FULL",
            "OUTER",
            "CROSS",
            "ON",
            "WHERE",
            "AND",
            "OR",
            "NOT",
            "NULL",
            "IS",
            "IN",
            "LIKE",
            "BETWEEN",
            "AS",
            "GROUP",
            "BY",
            "ORDER",
            "ASC",
            "DESC",
            "HAVING",
            "LIMIT",
            "OFFSET",
            "UNION",
            "ALL",
            "DISTINCT",
            "CASE",
            "WHEN",
            "THEN",
            "ELSE",
            "END",
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "CAST",
            "COALESCE",
        }

        # --------------------------------------------------------
        # SQL function names
        #
        # We do not want:
        #
        # COUNT(...)
        #
        # to become a column.
        # --------------------------------------------------------

        function_names = set(
            re.findall(
                r"""
                \b
                ([A-Za-z_][A-Za-z0-9_]*)
                \s*
                \(
                """,
                query_without_qualified,
                re.IGNORECASE | re.VERBOSE,
            )
        )

        function_names = {
            name.upper()
            for name in function_names
        }

        # --------------------------------------------------------
        # Extract identifiers
        # --------------------------------------------------------

        identifiers = re.findall(
            r"\b[A-Za-z_][A-Za-z0-9_]*\b",
            query_without_qualified,
        )

        # --------------------------------------------------------
        # Extract tables / aliases so they are not treated
        # as columns.
        #
        # Example:
        #
        # SELECT name FROM customers
        #
        # "customers" is a table, NOT a column.
        # --------------------------------------------------------

        table_names_and_aliases = set()

        table_matches = re.finditer(
            r"""
            \b(?:FROM|JOIN)\s+
            ([A-Za-z_][A-Za-z0-9_]*)
            (?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?
            """,
            query_without_qualified,
            re.IGNORECASE | re.VERBOSE,
        )

        for match in table_matches:

            table_name = match.group(1)
            alias = match.group(2)

            if table_name:
                table_names_and_aliases.add(
                    table_name.lower()
                )

            if alias:
                table_names_and_aliases.add(
                    alias.lower()
                )

        # --------------------------------------------------------
        # Extract SELECT aliases
        #
        # Example:
        #
        # SELECT AVG(faithfulness_0_1) AS avg_faithfulness
        # FROM rag_evaluation
        #
        # "avg_faithfulness" is an output alias,
        # NOT a real database column.
        # --------------------------------------------------------

        select_aliases = set()

        alias_matches = re.findall(
            r"""
            \bAS\s+
            ([A-Za-z_][A-Za-z0-9_]*)
            \b
            """,
            query_without_qualified,
            re.IGNORECASE | re.VERBOSE,
        )

        for alias in alias_matches:
            select_aliases.add(
                alias.lower()
            )

        # --------------------------------------------------------
        # Keep only actual column candidates
        # --------------------------------------------------------

        for identifier in identifiers:

            upper_identifier = identifier.upper()
            lower_identifier = identifier.lower()

            # SQL keywords
            if upper_identifier in ignored_keywords:
                continue

            # SQL functions
            if upper_identifier in function_names:
                continue

            # Table names / aliases
            if lower_identifier in table_names_and_aliases:
                continue

            # SELECT aliases
            #
            # Example:
            #
            # AVG(score) AS avg_score
            #
            # avg_score is NOT a database column.
            if lower_identifier in select_aliases:
                continue

            columns.append(identifier)

        return columns


    @staticmethod
    def _validate_columns(
        columns: List[str],
        tables: Dict[str, str],
        schema: Dict[str, Any],
    ) -> None:

        # --------------------------------------------------------
        # Build available columns for every table
        # --------------------------------------------------------

        table_columns = {

            table_name: {
                column["name"]
                for column in table_info.get(
                    "columns",
                    [],
                )
            }

            for table_name, table_info
            in schema.items()
        }

        # --------------------------------------------------------
        # Validate each column
        # --------------------------------------------------------

        for column_reference in columns:

            # ====================================================
            # Qualified column
            #
            # Example:
            #
            # c.name
            # ====================================================

            if "." in column_reference:

                alias, column_name = (
                    column_reference.split(
                        ".",
                        1,
                    )
                )

                # ----------------------------------------------
                # Alias must exist
                # ----------------------------------------------

                if alias not in tables:

                    raise SQLValidationError(
                        f"Unknown table alias: {alias}"
                    )

                table_name = tables[alias]

                # ----------------------------------------------
                # Column must exist
                # ----------------------------------------------

                if column_name not in table_columns.get(
                    table_name,
                    set(),
                ):

                    raise SQLValidationError(
                        f"Unknown column: "
                        f"{table_name}.{column_name}"
                    )

                continue

            # ====================================================
            # Unqualified column
            #
            # Example:
            #
            # SELECT name FROM customers
            # ====================================================

            column_name = column_reference

            matching_tables = [
                table_name
                for table_name in set(
                    tables.values()
                )
                if column_name in table_columns.get(
                    table_name,
                    set(),
                )
            ]

            # ----------------------------------------------
            # Column does not exist anywhere
            # ----------------------------------------------

            if not matching_tables:

                raise SQLValidationError(
                    f"Unknown column: {column_name}"
                )

            # ----------------------------------------------
            # Column exists in more than one table
            #
            # Example:
            #
            # customers.id
            # orders.id
            #
            # SELECT id
            #
            # This is ambiguous and should be rejected.
            # ----------------------------------------------

            if len(matching_tables) > 1:

                raise SQLValidationError(
                    f"Ambiguous column: {column_name}. "
                    "Qualify the column with a table alias."
                )
    @staticmethod
    def _extract_join_conditions(
        query: str,
    ) -> List[Tuple[str, str]]:

        """
        Extract:

            JOIN orders o
            ON c.id = o.customer_id

        into:

            [
                (
                    "c.id",
                    "o.customer_id"
                )
            ]
        """

        conditions: List[
            Tuple[str, str]
        ] = []

        pattern = re.compile(
            r"""
            \b
            JOIN
            \s+
            [A-Za-z_][A-Za-z0-9_]*
            (?:
                \s+
                AS?
                \s+
                [A-Za-z_][A-Za-z0-9_]*
            )?
            \s+
            ON
            \s+
            (?P<left_alias>
                [A-Za-z_][A-Za-z0-9_]*
            )
            \.
            (?P<left_column>
                [A-Za-z_][A-Za-z0-9_]*
            )
            \s*
            =
            \s*
            (?P<right_alias>
                [A-Za-z_][A-Za-z0-9_]*
            )
            \.
            (?P<right_column>
                [A-Za-z_][A-Za-z0-9_]*
            )
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        for match in pattern.finditer(query):

            left = (
                f"{match.group('left_alias')}."
                f"{match.group('left_column')}"
            )

            right = (
                f"{match.group('right_alias')}."
                f"{match.group('right_column')}"
            )

            conditions.append(
                (
                    left,
                    right,
                )
            )

        return conditions

    # ============================================================
    # Build Foreign Key Relationships
    # ============================================================

    @staticmethod
    def _build_relationships(
        schema: Dict[str, Any],
    ) -> List[
        Tuple[str, str, str, str]
    ]:

        """
        Convert schema FK definitions into:

            (
                source_table,
                source_column,
                target_table,
                target_column
            )
        """

        relationships = []

        for table_name, table_info in schema.items():

            foreign_keys = table_info.get(
                "foreign_keys",
                [],
            )

            for foreign_key in foreign_keys:

                source_column = foreign_key.get(
                    "column"
                )

                target_table = foreign_key.get(
                    "references_table"
                )

                target_column = foreign_key.get(
                    "references_column"
                )

                if not source_column:
                    continue

                if not target_table:
                    continue

                if not target_column:
                    continue

                relationships.append(
                    (
                        table_name,
                        source_column,
                        target_table,
                        target_column,
                    )
                )

        return relationships

    # ============================================================
    # Validate JOIN Relationships
    # ============================================================

    @classmethod
    def _validate_join_relationships(
        cls,
        query: str,
        tables: Dict[str, str],
        schema: Dict[str, Any],
    ) -> None:

        join_conditions = cls._extract_join_conditions(
            query
        )

        # No JOIN
        if not join_conditions:
            return

        relationships = cls._build_relationships(
            schema
        )

        # --------------------------------------------------------
        # Build normalized relationship set
        # --------------------------------------------------------

        normalized_relationships = set()

        for (
            source_table,
            source_column,
            target_table,
            target_column,
        ) in relationships:

            # Original FK direction
            normalized_relationships.add(
                (
                    source_table,
                    source_column,
                    target_table,
                    target_column,
                )
            )

            # Reverse direction
            normalized_relationships.add(
                (
                    target_table,
                    target_column,
                    source_table,
                    source_column,
                )
            )

        # --------------------------------------------------------
        # Validate every JOIN
        # --------------------------------------------------------

        for left, right in join_conditions:

            left_alias, left_column = left.split(
                ".",
                1,
            )

            right_alias, right_column = right.split(
                ".",
                1,
            )

            # ----------------------------------------------------
            # Validate aliases
            # ----------------------------------------------------

            if left_alias not in tables:

                raise SQLValidationError(
                    f"Unknown JOIN table alias: "
                    f"{left_alias}"
                )

            if right_alias not in tables:

                raise SQLValidationError(
                    f"Unknown JOIN table alias: "
                    f"{right_alias}"
                )

            left_table = tables[left_alias]
            right_table = tables[right_alias]

            # ----------------------------------------------------
            # Build relationship
            # ----------------------------------------------------

            relationship = (
                left_table,
                left_column,
                right_table,
                right_column,
            )

            # ----------------------------------------------------
            # Validate FK relationship
            # ----------------------------------------------------

            if relationship not in normalized_relationships:

                raise SQLValidationError(
                    "Invalid JOIN relationship: "
                    f"{left_table}.{left_column} = "
                    f"{right_table}.{right_column}. "
                    "The relationship is not supported "
                    "by the database schema."
                )

    # ============================================================
    # Apply LIMIT
    # ============================================================

    @staticmethod
    def _apply_limit(
        query: str,
        max_rows: int,
    ) -> str:

        if max_rows <= 0:

            raise SQLValidationError(
                "max_rows must be greater than zero."
            )

        if re.search(
            r"\bLIMIT\s+\d+\b",
            query,
            re.IGNORECASE,
        ):
            return query

        return (
            f"{query}\n"
            f"LIMIT {max_rows}"
        )

