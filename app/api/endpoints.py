"""端点管理API路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Endpoint

router = APIRouter(prefix="/endpoints", tags=["端点管理"])


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


@router.get("")
async def list_endpoints(db: AsyncSession = Depends(get_db)):
    """获取所有端点"""
    result = await db.execute(select(Endpoint))
    endpoints = result.scalars().all()
    return {"items": [e.to_dict() for e in endpoints]}


@router.get("/{endpoint_id}")
async def get_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个端点"""
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")
    return endpoint.to_dict()


@router.post("")
async def create_endpoint(data: EndpointCreate, db: AsyncSession = Depends(get_db)):
    """创建端点"""
    endpoint = Endpoint(**data.model_dump())
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return endpoint.to_dict()


@router.put("/{endpoint_id}")
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


@router.delete("/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, db: AsyncSession = Depends(get_db)):
    """删除端点"""
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")

    await db.delete(endpoint)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/reload")
async def reload_endpoints():
    """重新加载所有端点"""
    # TODO: 实现热重载
    return {"message": "端点已重新加载"}
