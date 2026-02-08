"""数据库连接管理"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from .config import get_settings

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    # 导入所有模型以确保它们被注册
    from app.models.endpoint import Endpoint, EndpointParameter, EndpointResponse
    from app.models.datamodel import DataModel, ModelField
    from app.models.workflow import Workflow, WorkflowNode, WorkflowConnection
    from app.models.execution_log import WorkflowExecutionLog

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
