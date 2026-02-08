"""SuperWeb 主应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from app.core.config import get_settings
from app.core.database import init_db
from app.engine import loader
from app import api, ui

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await init_db()
    print(f"Database initialized at {settings.DATABASE_URL}")

    # 加载动态路由
    dynamic_router = await loader.load_all_endpoints()
    app.include_router(dynamic_router)

    print(f"SuperWeb {settings.APP_VERSION} started!")
    print(f"UI: http://{settings.HOST}:{settings.PORT}/ui/")
    print(f"API Docs: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    # 关闭时执行
    print("SuperWeb shutting down...")


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="可视化API开发框架 - 通过界面配置开发接口",
    lifespan=lifespan
)

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(__file__), "ui", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 加载管理API (在启动时就注册)
app.include_router(api.router)

# 加载UI界面 (在启动时就注册)
if settings.UI_ENABLED:
    app.include_router(ui.router)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)}
    )


# 基础路由
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "SuperWeb - 可视化API开发框架",
        "docs": "/docs",
        "ui": "/ui/"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/workflow/api")
async def execute_workflow_api(request: Request):
    """统一的工作流调用接口 - 通过JSON body传递流程名称"""
    from sqlalchemy import select
    from app.core.database import async_session_maker
    from app.models.workflow import Workflow
    from app.engine.executor import execute_python_workflow_with_logging

    # 获取请求参数
    try:
        body = await request.json()
    except:
        return JSONResponse(
            status_code=400,
            content={"error": "请求必须是有效的JSON格式"}
        )

    # 从body中获取流程名称
    workflow_name = body.get("workflow_name") if isinstance(body, dict) else None
    if not workflow_name:
        return JSONResponse(
            status_code=400,
            content={"error": "缺少必需参数 'workflow_name'"}
        )

    # 获取其他参数
    query_params = dict(request.query_params)
    path_params = {"workflow_name": workflow_name}
    headers = dict(request.headers)

    # 记录请求方法到body
    if isinstance(body, dict):
        body["_method"] = "POST"

    # 合并所有参数
    context = {
        "path": path_params,
        "query": query_params,
        "body": body,
        "headers": headers,
        "request": request,
    }

    async with async_session_maker() as session:
        # 根据工作流名称查找工作流
        result = await session.execute(
            select(Workflow).where(Workflow.name == workflow_name, Workflow.enabled == True)
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            return JSONResponse(
                status_code=404,
                content={"error": f"工作流 '{workflow_name}' 不存在或未启用"}
            )

        # 获取工作流的所有节点
        from app.models.workflow import WorkflowNode
        nodes_result = await session.execute(
            select(WorkflowNode)
            .where(WorkflowNode.workflow_id == workflow.id)
            .order_by(WorkflowNode.position_x)
        )
        nodes = nodes_result.scalars().all()

        if not nodes:
            return {"error": "工作流为空", "workflow": workflow_name}

        # 构建节点映射
        node_map = {}
        for node in nodes:
            node_num = int(node.node_id.split('_')[1]) if node.node_id.startswith('node_') else int(node.position_x / 200)
            node_map[node_num] = node

        # 检查是否启用日志
        enable_logging = workflow.logging_enabled

        # 执行工作流（带日志）
        try:
            result = await execute_python_workflow_with_logging(
                node_map,
                context,
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                enable_logging=enable_logging
            )

            return result
        except Exception as e:
            import traceback
            return JSONResponse(
                status_code=500,
                content={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "workflow": workflow_name
                }
            )


def main():
    """启动服务器"""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
