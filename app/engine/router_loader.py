"""动态路由加载器"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import importlib
import sys
import asyncio
import json
from io import StringIO

from app.core.database import async_session_maker
from app.models.endpoint import Endpoint, EndpointParameter
from app.engine.executor import execute_endpoint


class RouterLoader:
    """动态路由加载器"""

    def __init__(self):
        self.loaded_routes: Dict[str, Any] = {}

    async def load_all_endpoints(self) -> APIRouter:
        """加载所有启用的端点"""
        router = APIRouter()

        async with async_session_maker() as session:
            result = await session.execute(
                select(Endpoint).where(Endpoint.enabled == True)
            )
            endpoints = result.scalars().all()

            for endpoint in endpoints:
                self._register_endpoint(router, endpoint)

        return router

    def _register_endpoint(self, router: APIRouter, endpoint: Endpoint):
        """注册单个端点"""
        route_key = f"{endpoint.method}:{endpoint.path}"

        if route_key in self.loaded_routes:
            return

        async def endpoint_handler(request: Request):
            """端点处理器"""
            try:
                # 获取路径参数
                path_params = request.path_params
                return await execute_endpoint(endpoint, request, path_params)
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        # 注册路由
        router.add_api_route(
            endpoint.path,
            endpoint_handler,
            methods=[endpoint.method],
            summary=endpoint.summary or endpoint.name,
            description=endpoint.description
        )

        self.loaded_routes[route_key] = endpoint

    async def reload_endpoints(self) -> APIRouter:
        """重新加载所有端点"""
        self.loaded_routes.clear()
        return await self.load_all_endpoints()


# 全局加载器实例
loader = RouterLoader()
