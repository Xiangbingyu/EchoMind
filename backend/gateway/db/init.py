from gateway.db.base import Base, engine
from gateway.models.models import Workspace, ProjectWorkspace, Session, Message, Agent


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
