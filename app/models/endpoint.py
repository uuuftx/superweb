"""API端点配置模型"""

from sqlalchemy import String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from typing import List, Optional
import json


class Endpoint(Base):
    """API端点配置"""
    __tablename__ = "endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="端点名称")
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, comment="路由路径")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET", comment="HTTP方法")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    summary: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="API文档摘要")

    # 逻辑配置
    logic_type: Mapped[str] = mapped_column(
        String(50),
        default="simple",
        comment="逻辑类型: simple, workflow, crud"
    )
    workflow_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="关联工作流ID")
    model_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="关联数据模型ID")

    # 自定义代码
    custom_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="自定义Python代码")

    # 响应配置
    response_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="响应模板(JSON)")

    parameters: Mapped[List["EndpointParameter"]] = relationship(
        "EndpointParameter",
        back_populates="endpoint",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "method": self.method,
            "description": self.description,
            "enabled": self.enabled,
            "summary": self.summary,
            "logic_type": self.logic_type,
            "workflow_id": self.workflow_id,
            "model_id": self.model_id,
            "custom_code": self.custom_code,
            "response_template": self.response_template,
        }


class EndpointParameter(Base):
    """端点参数配置"""
    __tablename__ = "endpoint_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("endpoints.id"), nullable=False, comment="端点ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="参数名")
    param_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="参数位置: query, path, body, header"
    )
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="数据类型")
    required: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必填")
    default_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="默认值")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="参数描述")

    endpoint: Mapped["Endpoint"] = relationship("Endpoint", back_populates="parameters")


class EndpointResponse(Base):
    """端点响应配置"""
    __tablename__ = "endpoint_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("endpoints.id"), nullable=False, comment="端点ID")
    status_code: Mapped[int] = mapped_column(Integer, default=200, comment="HTTP状态码")
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="响应描述")
    schema: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="响应Schema(JSON)")
