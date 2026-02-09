"""数据库连接管理"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Dict
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
    from app.models.database_config import DatabaseConfig

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ==================== 外部数据库连接池管理 ====================

# 外部数据库引擎缓存 {config_id: engine}
_external_engines: Dict[int, any] = {}
# 外部数据库会话工厂缓存 {config_id: session_maker}
_external_session_makers: Dict[int, any] = {}


def get_external_db_engine(config_id: int):
    """获取外部数据库引擎"""
    return _external_engines.get(config_id)


def get_external_db_session_maker(config_id: int):
    """获取外部数据库会话工厂"""
    return _external_session_makers.get(config_id)


async def create_external_db_engine(db_config):
    """
    创建外部数据库引擎和会话工厂

    Args:
        db_config: DatabaseConfig 实例

    Returns:
        (engine, session_maker)
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    connection_string = db_config.get_connection_string()

    # 转换为异步连接字符串
    if db_config.db_type == "sqlite":
        async_conn_str = connection_string.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif db_config.db_type == "postgresql":
        async_conn_str = connection_string.replace("postgresql://", "postgresql+asyncpg://")
    elif db_config.db_type == "mysql":
        async_conn_str = connection_string  # 已经是 pymysql
    elif db_config.db_type == "mssql":
        async_conn_str = connection_string  # 已经是 pymssql
    else:
        raise ValueError(f"不支持的数据库类型: {db_config.db_type}")

    # SQLite 不支持连接池参数
    if db_config.db_type == "sqlite":
        engine = create_async_engine(
            async_conn_str,
            echo=settings.DEBUG,
            future=True
        )
    else:
        engine = create_async_engine(
            async_conn_str,
            echo=settings.DEBUG,
            pool_size=db_config.pool_size,
            max_overflow=db_config.max_overflow,
            pool_timeout=db_config.pool_timeout,
            pool_recycle=db_config.pool_recycle,
            future=True
        )

    # 创建会话工厂
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # 缓存引擎和会话工厂
    _external_engines[db_config.id] = engine
    _external_session_makers[db_config.id] = session_maker

    return engine, session_maker


async def close_external_db_connection(config_id: int):
    """关闭外部数据库连接"""
    if config_id in _external_engines:
        await _external_engines[config_id].dispose()
        del _external_engines[config_id]

    if config_id in _external_session_makers:
        del _external_session_makers[config_id]


async def reload_external_db_connection(db_config):
    """重新加载外部数据库连接"""
    # 先关闭旧连接
    await close_external_db_connection(db_config.id)
    # 创建新连接
    return await create_external_db_engine(db_config)


async def get_all_active_db_configs():
    """
    获取所有启用的数据库配置

    Returns:
        dict: {config_name: session_maker}
    """
    from sqlalchemy import select
    from app.models.database_config import DatabaseConfig

    async with async_session_maker() as session:
        result = await session.execute(
            select(DatabaseConfig).where(DatabaseConfig.enabled == True)
        )
        configs = result.scalars().all()

    # 确保所有配置都有引擎和会话工厂
    active_configs = {}
    for config in configs:
        if config.id not in _external_engines:
            try:
                await create_external_db_engine(config)
            except Exception as e:
                print(f"无法创建数据库连接 {config.name}: {e}")
                continue

        active_configs[config.name] = {
            "config": config,
            "session_maker": _external_session_makers.get(config.id),
            "engine": _external_engines.get(config.id)
        }

    return active_configs

