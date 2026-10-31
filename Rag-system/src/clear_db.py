import asyncio
from sqlalchemy import delete
from helpers.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.db_schemes import DataChunk, Asset

async def clear_project(project_id: int):
    settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Deleting all chunks and assets for project {project_id}...")
    
    async with db_client() as session:
        await session.execute(delete(DataChunk).where(DataChunk.chunk_project_id == project_id))
        await session.execute(delete(Asset).where(Asset.asset_project_id == project_id))
        await session.commit()
        print("✅ Database cleared successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_project(1))