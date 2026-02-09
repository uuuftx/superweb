"""管理API路由 - 统一入口"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models import DataModel
from app.engine.router_loader import loader

# 导入子路由
from app.api import endpoints, workflows, database_configs

# 创建主路由
router = APIRouter(prefix="/api/admin", tags=["管理"])

# 注册子路由
router.include_router(endpoints.router)
router.include_router(workflows.router)
router.include_router(database_configs.router)


# ========== 数据模型管理 ==========

class DataModelCreate(BaseModel):
    name: str
    table_name: str
    description: str | None = None


class ModelFieldCreate(BaseModel):
    name: str
    field_type: str
    length: int | None = None
    required: bool = False
    unique: bool = False
    primary_key: bool = False
    default_value: str | None = None
    description: str | None = None


@router.get("/models")
async def list_models(db: AsyncSession = Depends(get_db)):
    """获取所有数据模型"""
    result = await db.execute(select(DataModel))
    models = result.scalars().all()
    return {"items": [m.to_dict() for m in models]}


@router.post("/models")
async def create_model(data: DataModelCreate, db: AsyncSession = Depends(get_db)):
    """创建数据模型"""
    model = DataModel(**data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)

    # 创建对应的数据库表
    await _create_model_table(db, model)

    return model.to_dict()


@router.post("/models/{model_id}/fields")
async def add_model_field(model_id: int, data: ModelFieldCreate, db: AsyncSession = Depends(get_db)):
    """添加模型字段"""
    result = await db.execute(select(DataModel).where(DataModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    from app.models.datamodel import ModelField
    field = ModelField(model_id=model_id, **data.model_dump())
    db.add(field)
    await db.commit()
    await db.refresh(field)

    # 更新数据库表结构
    await _update_model_table(db, model)

    return {"message": "字段添加成功"}


# ========== 辅助函数 ==========

async def _create_model_table(db: AsyncSession, model: DataModel):
    """创建数据模型对应的数据库表"""
    from sqlalchemy import Table, Column, Integer, String, Float, Boolean, DateTime, Text, MetaData
    from app.core.database import engine

    metadata = MetaData()

    # 创建表
    table = Table(
        model.table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("created_at", DateTime, server_default="CURRENT_TIMESTAMP"),
        Column("updated_at", DateTime, server_default="CURRENT_TIMESTAMP"),
    )

    # 使用引擎的 run_sync 执行同步 DDL 操作
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all, checkfirst=True)


async def _update_model_table(db: AsyncSession, model: DataModel):
    """更新数据模型对应的数据库表"""
    from sqlalchemy import Table, Column, Integer, String, Float, Boolean, DateTime, Text, MetaData
    from app.core.database import engine

    metadata = MetaData()

    # 获取所有字段
    from app.models.datamodel import ModelField

    result = await db.execute(select(ModelField).where(ModelField.model_id == model.id))
    fields = result.scalars().all()

    # 类型映射
    type_mapping = {
        "string": String,
        "integer": Integer,
        "float": Float,
        "boolean": Boolean,
        "datetime": DateTime,
        "text": Text,
    }

    # 创建表（如果字段有变化则重建）
    columns = [
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("created_at", DateTime, server_default="CURRENT_TIMESTAMP"),
        Column("updated_at", DateTime, server_default="CURRENT_TIMESTAMP"),
    ]

    for field in fields:
        col_type = type_mapping.get(field.field_type, String)
        if field.length and col_type == String:
            col_type = col_type(field.length)

        columns.append(
            Column(
                field.name,
                col_type,
                nullable=not field.required,
                unique=field.unique,
            )
        )

    table = Table(model.table_name, metadata, *columns)

    # 使用引擎的 run_sync 执行同步 DDL 操作
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all, checkfirst=True)
