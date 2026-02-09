"""SuperWeb 主应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import time

from app.core.config import get_settings
from app.core.database import init_db
from app.core.request_logger import request_logger
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


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求"""
    start_time = time.time()

    # 处理请求
    response = await call_next(request)

    # 计算耗时
    duration = time.time() - start_time

    # 记录请求（排除静态文件和健康检查）
    if not request.url.path.startswith("/static") and request.url.path != "/health":
        request_logger.log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=duration,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            query_params=dict(request.query_params) if request.query_params else None,
            path_params=request.path_params
        )

    return response


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


# ========== 开发者工具 ==========

@app.get("/api/dev/request-logs")
async def get_request_logs(limit: int = 50):
    """获取最近的请求日志"""
    logs = request_logger.get_recent_logs(limit)
    return {"logs": logs}


@app.get("/api/dev/request-stats")
async def get_request_stats():
    """获取请求统计信息"""
    return request_logger.get_stats()


@app.post("/api/dev/request-logs/clear")
async def clear_request_logs():
    """清空请求日志"""
    request_logger.clear()
    return {"message": "日志已清空"}


@app.get("/api/dev/storage-files")
async def get_storage_files():
    """获取存储文件列表"""
    from pathlib import Path
    import os

    storage_dir = Path("storage")
    if not storage_dir.exists():
        return {"files": []}

    files = []
    for root, dirs, filenames in os.walk(storage_dir):
        for filename in filenames:
            filepath = Path(root) / filename
            stat = filepath.stat()
            files.append({
                "name": filename,
                "path": str(filepath.relative_to(storage_dir)),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    return {"files": files}


@app.delete("/api/dev/storage-files")
async def delete_storage_file(request: Request):
    """删除存储文件"""
    from pathlib import Path

    body = await request.json()
    path = body.get("path")

    if not path:
        return JSONResponse(status_code=400, content={"error": "缺少 path 参数"})

    # 安全检查
    if ".." in path or path.startswith("/"):
        return JSONResponse(status_code=400, content={"error": "非法路径"})

    filepath = Path("storage") / path
    if not filepath.exists():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    filepath.unlink()
    return {"message": "文件已删除"}


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
