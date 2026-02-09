"""工作流管理API路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from pathlib import Path

from app.core.database import get_db
from app.models import Workflow
from app.models.workflow import WorkflowNode, WorkflowConnection
from app.utils import validate_workflow_name, validate_filename, WorkflowException, ValidationException

router = APIRouter(prefix="/workflows", tags=["工作流管理"])


# ========== 请求模型 ==========

class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证工作流名称"""
        is_valid, error_msg = validate_workflow_name(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    logging_enabled: bool | None = None


class WorkflowNodesSave(BaseModel):
    """保存工作流节点和连接"""
    nodes: list[dict]
    connections: list[dict]


# ========== 工作流CRUD ==========

@router.get("")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    """获取所有工作流"""
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    return {"items": [w.to_dict() for w in workflows]}


@router.post("")
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    """创建工作流"""
    workflow = Workflow(**data.model_dump())
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow.to_dict()


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """获取工作流详情"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow.to_dict()


@router.patch("/{workflow_id}")
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


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """删除工作流"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    await db.delete(workflow)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{workflow_id}/export")
async def export_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """导出工作流为 JSON"""
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

    # 构建导出数据
    export_data = {
        "version": "1.0",
        "workflow": {
            "name": workflow.name,
            "description": workflow.description,
            "enabled": workflow.enabled,
            "logging_enabled": workflow.logging_enabled
        },
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "name": n.name,
                "position_x": n.position_x,
                "position_y": n.position_y,
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
        ],
        "exported_at": datetime.now().isoformat()
    }

    return export_data


class WorkflowImport(BaseModel):
    """工作流导入数据"""
    workflow: dict
    nodes: list[dict]
    connections: list[dict]


@router.post("/import")
async def import_workflow(data: WorkflowImport, db: AsyncSession = Depends(get_db)):
    """导入工作流"""
    # 检查名称是否已存在
    existing = await db.execute(
        select(Workflow).where(Workflow.name == data.workflow["name"])
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="工作流名称已存在")

    # 创建工作流
    workflow = Workflow(
        name=data.workflow["name"],
        description=data.workflow.get("description"),
        enabled=data.workflow.get("enabled", True),
        logging_enabled=data.workflow.get("logging_enabled", False)
    )
    db.add(workflow)
    await db.flush()  # 获取 workflow ID

    # 创建节点
    for node_data in data.nodes:
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_id=node_data["node_id"],
            node_type=node_data["node_type"],
            name=node_data["name"],
            position_x=node_data["position_x"],
            position_y=node_data["position_y"],
            config=node_data.get("config", {})
        )
        db.add(node)

    # 创建连接
    for conn_data in data.connections:
        conn = WorkflowConnection(
            workflow_id=workflow.id,
            source_node=conn_data["source"],
            target_node=conn_data["target"]
        )
        db.add(conn)

    await db.commit()
    await db.refresh(workflow)

    return {
        "message": "导入成功",
        "workflow": workflow.to_dict()
    }


# ========== 工作流节点和连接 ==========

@router.get("/{workflow_id}/detail")
async def get_workflow_detail(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """获取工作流详细信息（包含节点和连接）"""
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


@router.post("/{workflow_id}/nodes")
async def save_workflow_nodes(workflow_id: int, data: WorkflowNodesSave, db: AsyncSession = Depends(get_db)):
    """保存工作流的节点和连接"""
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


# ========== 工作流日志 ==========

@router.get("/{workflow_id}/logs")
async def get_workflow_logs(workflow_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """获取工作流执行日志"""
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
            # 读取文件的前几行来获取工作流信息
            with open(file_path, "r", encoding="utf-8") as f:
                first_lines = [f.readline().strip() for _ in range(20)]

            # 解析日志内容
            log_info = _parse_log_file(first_lines)

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
        except Exception:
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


@router.get("/{workflow_id}/logs/{log_filename}")
async def get_workflow_log_detail(workflow_id: int, log_filename: str, db: AsyncSession = Depends(get_db)):
    """获取单个日志文件的详细内容"""
    # 验证文件名安全性
    is_valid, error_msg = validate_filename(log_filename, allowed_extensions=["log"])
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 验证工作流是否存在
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

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


# ========== 辅助函数 ==========

def _parse_log_file(lines):
    """解析日志文件的前几行，提取关键信息"""
    info = {}

    for line in lines:
        line = line.strip()
        if "执行ID:" in line:
            info["execution_id"] = line.split("执行ID:")[-1].strip()
        elif "工作流名称:" in line:
            info["workflow_name"] = line.split("工作流名称:")[-1].strip()
        elif "开始时间:" in line:
            info["start_time"] = line.split("开始时间:")[-1].strip()
        elif "状态:" in line:
            info["status"] = line.split("状态:")[-1].strip()
        elif "执行时长:" in line:
            duration_str = line.split("执行时长:")[-1].strip().replace(" 秒", "")
            try:
                info["duration"] = float(duration_str)
            except:
                pass

    return info
