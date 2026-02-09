"""数据库配置管理API路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db, close_external_db_connection, reload_external_db_connection
from app.models.database_config import DatabaseConfig

router = APIRouter(prefix="/database-configs", tags=["数据库配置"])


# ========== 请求模型 ==========

class DatabaseConfigCreate(BaseModel):
    """创建数据库配置"""
    name: str
    description: str | None = None
    db_type: str  # sqlite, postgresql, mysql, mssql, oracle
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    path: str | None = None  # SQLite 文件路径
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    extra_config: dict = {}
    enabled: bool = True
    is_default: bool = False


class DatabaseConfigUpdate(BaseModel):
    """更新数据库配置"""
    name: str | None = None
    description: str | None = None
    db_type: str | None = None
    host: str | None = None
    port: str | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    path: str | None = None
    pool_size: int | None = None
    max_overflow: int | None = None
    pool_timeout: int | None = None
    pool_recycle: int | None = None
    extra_config: dict | None = None
    enabled: bool | None = None
    is_default: bool | None = None


# ========== 数据库配置CRUD ==========

@router.get("")
async def list_database_configs(db: AsyncSession = Depends(get_db)):
    """获取所有数据库配置"""
    result = await db.execute(select(DatabaseConfig))
    configs = result.scalars().all()
    return {
        "items": [
            {**c.to_dict(include_secrets=False), "has_password": bool(c.password)}
            for c in configs
        ]
    }


@router.get("/active")
async def get_active_database_configs():
    """获取所有激活的数据库配置"""
    from app.core.database import get_all_active_db_configs

    configs = await get_all_active_db_configs()

    return {
        "items": [
            {
                "id": v["config"].id,
                "name": v["config"].name,
                "description": v["config"].description,
                "db_type": v["config"].db_type,
                "enabled": v["config"].enabled,
                "is_default": v["config"].is_default,
            }
            for v in configs.values()
        ]
    }


@router.get("/{config_id}")
async def get_database_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个数据库配置"""
    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    return config.to_dict(include_secrets=True)


@router.post("")
async def create_database_config(data: DatabaseConfigCreate, db: AsyncSession = Depends(get_db)):
    """创建数据库配置"""
    # 检查名称是否已存在
    existing = await db.execute(
        select(DatabaseConfig).where(DatabaseConfig.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="配置名称已存在")

    # 如果设置为默认，取消其他默认配置
    if data.is_default:
        await _clear_default_flags(db)

    now = datetime.now().isoformat()
    config = DatabaseConfig(
        **data.model_dump(),
        created_at=now,
        updated_at=now
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    return config.to_dict(include_secrets=False)


@router.put("/{config_id}")
async def update_database_config(
    config_id: int,
    data: DatabaseConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新数据库配置"""
    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 如果设置为默认，取消其他默认配置
    if update_data.get("is_default"):
        await _clear_default_flags(db, exclude_id=config_id)

    # 更新字段
    for key, value in update_data.items():
        setattr(config, key, value)

    config.updated_at = datetime.now().isoformat()

    await db.commit()
    await db.refresh(config)

    # 重新加载连接
    try:
        await reload_external_db_connection(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"重新加载连接失败: {str(e)}")

    return config.to_dict(include_secrets=False)


@router.delete("/{config_id}")
async def delete_database_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """删除数据库配置"""
    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    # 关闭连接
    await close_external_db_connection(config_id)

    await db.delete(config)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{config_id}/test")
async def test_database_connection(config_id: int, db: AsyncSession = Depends(get_db)):
    """测试数据库连接"""
    from app.core.database import create_external_db_engine

    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    try:
        # 创建临时连接测试
        engine, _ = await create_external_db_engine(config)

        # 测试连接
        async with engine.begin() as conn:
            if config.db_type == "sqlite":
                await conn.execute("SELECT 1")
            else:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))

        # 关闭测试连接
        await close_external_db_connection(config_id)

        return {
            "success": True,
            "message": "连接测试成功"
        }
    except Exception as e:
        # 确保关闭连接
        await close_external_db_connection(config_id)
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}"
        }


# ========== 辅助函数 ==========

async def _clear_default_flags(db: AsyncSession, exclude_id: int = None):
    """清除所有默认标志（除了指定的ID）"""
    query = select(DatabaseConfig).where(DatabaseConfig.is_default == True)
    if exclude_id:
        query = query.where(DatabaseConfig.id != exclude_id)

    existing = await db.execute(query)
    all_defaults = existing.scalars().all()
    for d in all_defaults:
        d.is_default = False
