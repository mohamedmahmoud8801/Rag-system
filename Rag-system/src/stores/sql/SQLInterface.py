from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

# One statement inside a transaction:
#   (sql, None)        -> executed once
#   (sql, [row, ...])  -> executed once per row (executemany), named params
Statement = Tuple[str, Optional[List[Dict[str, Any]]]]


class SQLInterface(ABC):

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def get_tables(self) -> List[str]:
        pass

    @abstractmethod
    def get_schema(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        max_rows: Optional[int] = None,
        read_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Run one statement in its own transaction (committed on success).

        max_rows  : stop fetching after this many rows (result["truncated"]).
        read_only : the database itself refuses writes and long queries.
        """

    @abstractmethod
    def execute_transaction(self, statements: List[Statement]) -> None:
        """Run several statements atomically: all of them or none."""

    @abstractmethod
    def validate_connection(self) -> bool:
        pass