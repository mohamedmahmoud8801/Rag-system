from .SQLEnums import SQLProviderEnum
from .SQLInterface import SQLInterface
from .providers.SQLiteProvider import SQLiteProvider
from .providers.PostgreSQLProvider import PostgreSQLProvider


class SQLProviderFactory:

    @staticmethod
    def create(
        provider: SQLProviderEnum,
        database_url: str
    ) -> SQLInterface:

        if provider == SQLProviderEnum.SQLITE:

            return SQLiteProvider(
                database_url=database_url
            )

        if provider == SQLProviderEnum.POSTGRESQL:

            return PostgreSQLProvider(
                database_url=database_url
            )

        raise ValueError(
            f"Unsupported SQL provider: {provider}"
        )
