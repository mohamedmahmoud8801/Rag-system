import asyncio

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from helpers.config import get_settings


FILE_ID = "3dcnox5etx82_NIPS2017attentionisallyyouneedPaper.pdf"
COLLECTION = "collection_768_1"


async def main():
    settings = get_settings()

    postgres_conn = (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USERNAME}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DATABASE}"
    )

    engine = create_async_engine(postgres_conn)

    db_client = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    terms = [
        "Adam",
        "Penn Treebank",
        "Llion Jones",
        "Label Smoothing",
    ]

    async with db_client() as session:

        # --------------------------------------------------------------
        # 1. Verify collection
        # --------------------------------------------------------------

        exists_sql = sql_text(
            """
            SELECT to_regclass(:collection) AS table_name
            """
        )

        result = await session.execute(
            exists_sql,
            {"collection": COLLECTION},
        )

        table_name = result.scalar_one_or_none()

        print("=" * 80)
        print("COLLECTION")
        print("=" * 80)
        print(table_name)

        if table_name is None:
            print(f"\nERROR: collection/table '{COLLECTION}' does not exist.")
            await engine.dispose()
            return

        # --------------------------------------------------------------
        # 2. Count chunks for this file
        # --------------------------------------------------------------

        count_sql = sql_text(
            f"""
            SELECT COUNT(*)
            FROM {COLLECTION}
            WHERE metadata->>'source' = :file_id
            """
        )

        result = await session.execute(
            count_sql,
            {"file_id": FILE_ID},
        )

        count = result.scalar_one()

        print("\n" + "=" * 80)
        print("FILE CHUNK COUNT")
        print("=" * 80)
        print(f"file_id: {FILE_ID}")
        print(f"chunks : {count}")

        # --------------------------------------------------------------
        # 3. Search exact terms inside indexed chunks
        # --------------------------------------------------------------

        for term in terms:

            search_sql = sql_text(
                f"""
                SELECT
                    chunk_id,
                    text,
                    metadata
                FROM {COLLECTION}
                WHERE metadata->>'source' = :file_id
                  AND text ILIKE :pattern
                ORDER BY chunk_id
                """
            )

            result = await session.execute(
                search_sql,
                {
                    "file_id": FILE_ID,
                    "pattern": f"%{term}%",
                },
            )

            rows = result.fetchall()

            print("\n" + "=" * 80)
            print(f"SEARCH TERM: {term}")
            print("=" * 80)
            print(f"matches: {len(rows)}")

            for row in rows:
                print("\n" + "-" * 80)
                print(f"chunk_id: {row.chunk_id}")
                print(f"metadata: {row.metadata}")
                print("text:")
                print(row.text)

        # --------------------------------------------------------------
        # 4. Show source values if the file filter is wrong
        # --------------------------------------------------------------

        source_sql = sql_text(
            f"""
            SELECT
                metadata->>'source' AS source,
                COUNT(*) AS chunk_count
            FROM {COLLECTION}
            GROUP BY metadata->>'source'
            ORDER BY chunk_count DESC
            """
        )

        result = await session.execute(source_sql)

        rows = result.fetchall()

        print("\n" + "=" * 80)
        print("ALL SOURCES")
        print("=" * 80)

        for row in rows:
            print(f"{row.source!r} -> {row.chunk_count}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
