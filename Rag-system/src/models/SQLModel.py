from typing import Any, Dict, List, Optional

from stores.sql.SQLEnums import SQLProviderEnum
from stores.sql.SQLInterface import SQLInterface
from stores.sql.SQLProviderFactory import SQLProviderFactory


class SQLModel:

    def __init__(
        self,
        provider: SQLInterface
    ):
        self.provider = provider

    @classmethod
    async def create_instance(
        cls,
        provider: SQLInterface
    ):
        instance = cls(provider=provider)
        return instance

    async def get_tables(self) -> List[str]:
        return self.provider.get_tables()

    async def get_schema(
        self,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:

        return self.provider.get_schema(
            tables=tables
        )

    async def execute(
        self,
        query: str
    ) -> Dict[str, Any]:

        return self.provider.execute(
            query=query
        )