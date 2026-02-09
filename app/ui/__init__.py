"""网页配置界面"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter(prefix="/ui", tags=["界面"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    """工作流管理页面"""
    return templates.TemplateResponse("workflows.html", {"request": request})


@router.get("/workflow-editor", response_class=HTMLResponse)
async def workflow_editor_page(request: Request):
    """工作流编辑器 - 代码行号视图"""
    return templates.TemplateResponse("workflow_code_editor.html", {"request": request})


@router.get("/workflow-logs", response_class=HTMLResponse)
async def workflow_logs_page(request: Request):
    """工作流执行日志页面"""
    return templates.TemplateResponse("workflow_logs.html", {"request": request})


@router.get("/database-configs", response_class=HTMLResponse)
async def database_configs_page(request: Request):
    """数据库配置管理页面"""
    return templates.TemplateResponse("database_configs.html", {"request": request})


@router.get("/api-tester", response_class=HTMLResponse)
async def api_tester_page(request: Request):
    """API测试工具页面"""
    return templates.TemplateResponse("api_tester.html", {"request": request})


@router.get("/request-logs", response_class=HTMLResponse)
async def request_logs_page(request: Request):
    """请求日志查看页面"""
    return templates.TemplateResponse("request_logs.html", {"request": request})


@router.get("/dev-tools", response_class=HTMLResponse)
async def dev_tools_page(request: Request):
    """开发者工具页面"""
    return templates.TemplateResponse("dev_tools.html", {"request": request})
