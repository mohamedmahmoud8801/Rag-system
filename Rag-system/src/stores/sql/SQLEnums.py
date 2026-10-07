from enum import Enum


class SQLProviderEnum(str, Enum):

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class SQLDialectEnum(str, Enum):

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class SQLQueryTypeEnum(str, Enum):

    SELECT = "select"
