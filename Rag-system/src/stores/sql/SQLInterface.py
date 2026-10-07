from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


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
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        pass