"""工作流/逻辑编排模型"""

from sqlalchemy import String, Integer, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from typing import Optional


class Workflow(Base):
    """工作流定义"""
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="工作流名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    logging_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否启用日志记录")

    nodes: Mapped[list["WorkflowNode"]] = relationship(
        "WorkflowNode",
        back_populates="workflow",
        cascade="all, delete-orphan"
    )
    connections: Mapped[list["WorkflowConnection"]] = relationship(
        "WorkflowConnection",
        back_populates="workflow",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "logging_enabled": self.logging_enabled,
        }


class WorkflowNode(Base):
    """工作流节点"""
    __tablename__ = "workflow_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False, comment="工作流ID")
    node_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="节点唯一标识")
    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="节点类型: start, end, process, condition, database, api, transform"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="节点名称")
    position_x: Mapped[int] = mapped_column(Integer, default=0, comment="画布X坐标")
    position_y: Mapped[int] = mapped_column(Integer, default=0, comment="画布Y坐标")
    config: Mapped[dict] = mapped_column(JSON, default={}, comment="节点配置")

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="nodes")


class WorkflowConnection(Base):
    """工作流连接"""
    __tablename__ = "workflow_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False, comment="工作流ID")
    source_node: Mapped[str] = mapped_column(String(100), nullable=False, comment="源节点ID")
    target_node: Mapped[str] = mapped_column(String(100), nullable=False, comment="目标节点ID")
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="连接条件")

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="connections")
