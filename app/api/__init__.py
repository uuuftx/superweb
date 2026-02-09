"""管理API路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Endpoint, DataModel, Workflow
from app.engine.router_loader import loader

router = APIRouter(prefix="/api/admin", tags=["管理"])


# ========== 端点管理 ==========

class EndpointCreate(BaseModel):
    name: str
    path: str
    method: str = "GET"
    description: str | None = None
    summary: str | None = None
    logic_type: str = "simple"
    workflow_id: int | None = None
    model_id: int | None = None
    custom_code: str | None = None
    response_template: str | None = None


class EndpointUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    method: str | None = None
    description: str | None = None
    summary: str | None = None
    enabled: bool | None = None
    logic_type: str | None = None
    workflow_id: int | None = None
    model_id: int | None = None
    custom_code: str | None = None
    response_template: str | None = None


@router.get("/endpoints")
async def list_endpoints(db: AsyncSession = Depends(get_db)):
    """获取所有端点"""
    result = await db.execute(select(Endpoint))
    endpoints = result.scalars().all()
    return {"items": [e.to_dict() for e in endpoints]}


@router.get("/endpoints/{endpoint_id}")
async def get_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个端点"""
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")
    return endpoint.to_dict()


@router.post("/endpoints")
async def create_endpoint(data: EndpointCreate, db: AsyncSession = Depends(get_db)):
    """创建端点"""
    endpoint = Endpoint(**data.model_dump())
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return endpoint.to_dict()


@router.put("/endpoints/{endpoint_id}")
async def update_endpoint(endpoint_id: int, data: EndpointUpdate, db: AsyncSession = Depends(get_db)):
    """更新端点"""
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(endpoint, key, value)

    await db.commit()
    await db.refresh(endpoint)
    return endpoint.to_dict()


@router.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    """删除端点"""
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")

    await db.delete(endpoint)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/endpoints/reload")
async def reload_endpoints():
    """重新加载所有端点"""
    # TODO: 实现热重载
    return {"message": "端点已重新加载"}


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


# ========== 工作流管理 ==========

class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None


@router.get("/workflows")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    """获取所有工作流"""
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    return {"items": [w.to_dict() for w in workflows]}


@router.post("/workflows")
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    """创建工作流"""
    workflow = Workflow(**data.model_dump())
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow.to_dict()


class WorkflowNodesSave(BaseModel):
    """保存工作流节点和连接"""
    nodes: list[dict]
    connections: list[dict]


@router.post("/workflows/{workflow_id}/nodes")
async def save_workflow_nodes(workflow_id: int, data: WorkflowNodesSave, db: AsyncSession = Depends(get_db)):
    """保存工作流的节点和连接"""
    from app.models.workflow import WorkflowNode, WorkflowConnection

    try:
        # 先删除旧的连接（因为有外键约束）
        old_connections = (await db.execute(
            select(WorkflowConnection).where(WorkflowConnection.workflow_id == workflow_id)
        )).scalars().all()

        for conn in old_connections:
            await db.delete(conn)

        # 删除旧的节点
        old_nodes = (await db.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        )).scalars().all()

        for node in old_nodes:
            await db.delete(node)

        # 创建新节点
        for node_data in data.nodes:
            node = WorkflowNode(
                workflow_id=workflow_id,
                node_id=node_data["node_id"],
                node_type=node_data["node_type"],
                name=node_data["name"],
                position_x=node_data["position_x"],
                position_y=node_data["position_y"],
                config=node_data.get("config", {})
            )
            db.add(node)

        # 创建新连接
        for conn_data in data.connections:
            conn = WorkflowConnection(
                workflow_id=workflow_id,
                source_node=conn_data.get("source_node") or conn_data.get("source"),
                target_node=conn_data.get("target_node") or conn_data.get("target")
            )
            db.add(conn)

        await db.commit()
        return {"message": "保存成功", "nodes_count": len(data.nodes), "connections_count": len(data.connections)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/workflows/{workflow_id}/detail")
async def get_workflow_detail(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """获取工作流详细信息（包含节点和连接）"""
    from app.models.workflow import WorkflowNode, WorkflowConnection

    # 获取工作流
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 获取节点
    nodes_result = await db.execute(
        select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
    )
    nodes = nodes_result.scalars().all()

    # 获取连接
    conns_result = await db.execute(
        select(WorkflowConnection).where(WorkflowConnection.workflow_id == workflow_id)
    )
    connections = conns_result.scalars().all()

    return {
        "workflow": workflow.to_dict(),
        "nodes": [
            {
                "id": n.node_id,
                "type": n.node_type,
                "name": n.name,
                "x": n.position_x,
                "y": n.position_y,
                "config": n.config
            }
            for n in nodes
        ],
        "connections": [
            {
                "source": c.source_node,
                "target": c.target_node
            }
            for c in connections
        ]
    }


class WorkflowUpdate(BaseModel):
    """更新工作流设置"""
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    logging_enabled: bool | None = None


@router.patch("/workflows/{workflow_id}")
async def update_workflow(workflow_id: int, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    """更新工作流设置"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(workflow, key, value)

    await db.commit()
    await db.refresh(workflow)
    return workflow.to_dict()


@router.get("/workflows/{workflow_id}/logs")
async def get_workflow_logs(workflow_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """获取工作流执行日志"""
    import os
    from pathlib import Path

    # 验证工作流是否存在
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 读取日志目录中的文件
    log_dir = Path("storage/workflow_logs")
    if not log_dir.exists():
        return {
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "total_logs": 0,
            "logs": []
        }

    # 获取所有日志文件
    log_files = []
    for file_path in log_dir.glob("*.log"):
        try:
            # 从文件名解析信息
            # 格式: YYYYMMDD_HHMMSS_UUID.log
            parts = file_path.stem.split("_")
            if len(parts) >= 3:
                # 读取文件的前几行来获取工作流信息
                with open(file_path, "r", encoding="utf-8") as f:
                    first_lines = [f.readline().strip() for _ in range(20)]

                # 解析日志内容
                log_info = parse_log_file(first_lines)

                # 只返回该工作流的日志
                if log_info.get("workflow_name") == workflow.name:
                    log_files.append({
                        "filename": file_path.name,
                        "execution_id": log_info.get("execution_id"),
                        "start_time": log_info.get("start_time"),
                        "status": log_info.get("status"),
                        "duration": log_info.get("duration"),
                        "file_path": str(file_path)
                    })
        except Exception as e:
            # 跳过无法解析的文件
            continue

    # 按时间排序（最新的在前）
    log_files.sort(key=lambda x: x.get("start_time", ""), reverse=True)

    # 限制返回数量
    log_files = log_files[:limit]

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow.name,
        "total_logs": len(log_files),
        "logs": log_files
    }


def parse_log_file(lines):
    """解析日志文件的前几行，提取关键信息"""
    info = {}

    for line in lines:
        line = line.strip()
        if line.startswith("执行ID:") or "执行ID:" in line:
            info["execution_id"] = line.split("执行ID:")[-1].strip()
        elif line.startswith("工作流名称:") or "工作流名称:" in line:
            info["workflow_name"] = line.split("工作流名称:")[-1].strip()
        elif line.startswith("开始时间:") or "开始时间:" in line:
            info["start_time"] = line.split("开始时间:")[-1].strip()
        elif line.startswith("状态:") or "状态:" in line:
            info["status"] = line.split("状态:")[-1].strip()
        elif line.startswith("执行时长:") or "执行时长:" in line:
            duration_str = line.split("执行时长:")[-1].strip().replace(" 秒", "")
            try:
                info["duration"] = float(duration_str)
            except:
                pass

    return info


@router.get("/workflows/{workflow_id}/logs/{log_filename}")
async def get_workflow_log_detail(workflow_id: int, log_filename: str, db: AsyncSession = Depends(get_db)):
    """获取单个日志文件的详细内容"""
    from pathlib import Path

    # 验证工作流是否存在
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 安全检查：确保文件名只包含安全字符
    if not log_filename.endswith(".log") or "/" in log_filename or "\\" in log_filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    # 构建文件路径
    log_dir = Path("storage/workflow_logs")
    file_path = log_dir / log_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    # 读取日志文件内容
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "filename": log_filename,
            "workflow_name": workflow.name,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志文件失败: {str(e)}")


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """删除工作流"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    await db.delete(workflow)
    await db.commit()
    return {"message": "删除成功"}


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
    from sqlalchemy import select

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


# ========== 数据库配置管理 ==========

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
    port: int | None = None
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


@router.get("/database-configs")
async def list_database_configs(db: AsyncSession = Depends(get_db)):
    """获取所有数据库配置"""
    from app.models.database_config import DatabaseConfig

    result = await db.execute(select(DatabaseConfig))
    configs = result.scalars().all()
    return {
        "items": [
            {**c.to_dict(include_secrets=False), "has_password": bool(c.password)}
            for c in configs
        ]
    }


@router.get("/database-configs/{config_id}")
async def get_database_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个数据库配置"""
    from app.models.database_config import DatabaseConfig

    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    return config.to_dict(include_secrets=True)


@router.post("/database-configs")
async def create_database_config(data: DatabaseConfigCreate, db: AsyncSession = Depends(get_db)):
    """创建数据库配置"""
    from app.models.database_config import DatabaseConfig
    from datetime import datetime

    # 检查名称是否已存在
    existing = await db.execute(
        select(DatabaseConfig).where(DatabaseConfig.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="配置名称已存在")

    # 如果设置为默认，取消其他默认配置
    if data.is_default:
        existing = await db.execute(
            select(DatabaseConfig).where(DatabaseConfig.is_default == True)
        )
        all_defaults = existing.scalars().all()
        for d in all_defaults:
            d.is_default = False

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


@router.put("/database-configs/{config_id}")
async def update_database_config(
    config_id: int,
    data: DatabaseConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新数据库配置"""
    from app.models.database_config import DatabaseConfig
    from datetime import datetime

    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 如果设置为默认，取消其他默认配置
    if update_data.get("is_default"):
        existing = await db.execute(
            select(DatabaseConfig).where(DatabaseConfig.is_default == True)
        )
        all_defaults = existing.scalars().all()
        for d in all_defaults:
            if d.id != config_id:
                d.is_default = False

    # 更新字段
    for key, value in update_data.items():
        setattr(config, key, value)

    config.updated_at = datetime.now().isoformat()

    await db.commit()
    await db.refresh(config)

    # 重新加载连接
    try:
        from app.core.database import reload_external_db_connection
        await reload_external_db_connection(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"重新加载连接失败: {str(e)}")

    return config.to_dict(include_secrets=False)


@router.delete("/database-configs/{config_id}")
async def delete_database_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """删除数据库配置"""
    from app.models.database_config import DatabaseConfig

    result = await db.execute(select(DatabaseConfig).where(DatabaseConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="数据库配置不存在")

    # 关闭连接
    from app.core.database import close_external_db_connection
    await close_external_db_connection(config_id)

    await db.delete(config)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/database-configs/{config_id}/test")
async def test_database_connection(config_id: int, db: AsyncSession = Depends(get_db)):
    """测试数据库连接"""
    from app.models.database_config import DatabaseConfig
    from app.core.database import create_external_db_engine, close_external_db_connection

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


@router.get("/database-configs/active")
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
