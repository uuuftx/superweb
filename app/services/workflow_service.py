"""工作流执行服务"""

from sqlalchemy import select
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.database import async_session_maker
from app.models.workflow import Workflow, WorkflowNode


async def execute_workflow_by_name(workflow_name: str, request: Request) -> Response:
    """
    统一的工作流调用服务

    Args:
        workflow_name: 工作流名称
        request: FastAPI Request 对象

    Returns:
        JSONResponse
    """
    # 解析请求体
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "请求必须是有效的JSON格式"}
        )

    # 验证工作流名称
    if not workflow_name:
        return JSONResponse(
            status_code=400,
            content={"error": "缺少必需参数 'workflow_name'"}
        )

    # 构建上下文
    context = _build_request_context(request, body, workflow_name)

    # 查找并执行工作流
    async with async_session_maker() as session:
        workflow = await _get_enabled_workflow(session, workflow_name)
        if not workflow:
            return JSONResponse(
                status_code=404,
                content={"error": f"工作流 '{workflow_name}' 不存在或未启用"}
            )

        node_map = await _get_workflow_nodes(session, workflow)
        if not node_map:
            return {"error": "工作流为空", "workflow": workflow_name}

        # 执行工作流
        return await _execute_workflow(workflow, node_map, context)


def _build_request_context(request: Request, body: dict, workflow_name: str) -> dict:
    """构建请求上下文"""
    # 记录请求方法到body
    if isinstance(body, dict):
        body = {**body, "_method": "POST"}

    return {
        "path": {"workflow_name": workflow_name},
        "query": dict(request.query_params),
        "body": body,
        "headers": dict(request.headers),
        "request": request,
    }


async def _get_enabled_workflow(session, workflow_name: str):
    """获取启用的工作流"""
    result = await session.execute(
        select(Workflow).where(
            Workflow.name == workflow_name,
            Workflow.enabled == True
        )
    )
    return result.scalar_one_or_none()


async def _get_workflow_nodes(session, workflow: Workflow) -> dict:
    """获取工作流节点并构建节点映射"""
    from app.engine.executor import execute_python_workflow_with_logging

    nodes_result = await session.execute(
        select(WorkflowNode)
        .where(WorkflowNode.workflow_id == workflow.id)
        .order_by(WorkflowNode.position_x)
    )
    nodes = nodes_result.scalars().all()

    # 构建节点映射（从 position_x 计算节点编号）
    return {
        int(node.position_x / 200): node
        for node in nodes
    }


async def _execute_workflow(workflow: Workflow, node_map: dict, context: dict) -> Response:
    """执行工作流"""
    from app.engine.executor import execute_python_workflow_with_logging
    import traceback

    try:
        result = await execute_python_workflow_with_logging(
            node_map,
            context,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            enable_logging=workflow.logging_enabled
        )
        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "traceback": traceback.format_exc(),
                "workflow": workflow.name
            }
        )
