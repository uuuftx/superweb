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
    from app.services.workflow_service import execute_workflow_by_name

    # 获取请求体并提取工作流名称
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "请求必须是有效的JSON格式"}
        )

    workflow_name = body.get("workflow_name") if isinstance(body, dict) else None

    return await execute_workflow_by_name(workflow_name, request)


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
