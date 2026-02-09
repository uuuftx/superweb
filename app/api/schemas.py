"""统一的API响应模型"""

from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field


T = TypeVar('T')


class BaseResponse(BaseModel, Generic[T]):
    """基础响应模型"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[T] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功",
                "data": None
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(0, description="总数量")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")
    total_pages: int = Field(1, description="总页数")

    @classmethod
    def create(cls, items: List[T], total: int, page: int = 1, page_size: int = 20):
        """创建分页响应"""
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    code: Optional[str] = Field(None, description="错误代码")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "请求失败",
                "detail": "详细的错误描述",
                "code": "ERROR_CODE"
            }
        }


class MessageResponse(BaseModel):
    """简单消息响应"""
    success: bool = True
    message: str = Field(..., description="消息内容")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功"
            }
        }


# ========== 辅助函数 ==========

def success_response(data: Any = None, message: str = "操作成功") -> dict:
    """创建成功响应"""
    return {
        "success": True,
        "message": message,
        "data": data
    }


def error_response(error: str, detail: str = None, code: str = None) -> dict:
    """创建错误响应"""
    response = {
        "success": False,
        "error": error
    }
    if detail:
        response["detail"] = detail
    if code:
        response["code"] = code
    return response


def paginated_response(items: List[Any], total: int, page: int = 1, page_size: int = 20) -> dict:
    """创建分页响应"""
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }
