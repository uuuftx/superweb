"""工作流执行日志模型"""

from sqlalchemy import String, Integer, Text, Boolean, JSON, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from typing import Optional
from datetime import datetime


class WorkflowExecutionLog(Base):
    """工作流执行日志"""
    __tablename__ = "workflow_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False, comment="工作流ID")
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="工作流名称")
    execution_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="执行ID")

    # 执行信息
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="结束时间")
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="执行时长(秒)")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="状态: success, error, running")
    final_node: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最终节点")
    iterations: Mapped[int] = mapped_column(Integer, default=0, comment="迭代次数")

    # 请求信息
    request_method: Mapped[str] = mapped_column(String(10), nullable=False, comment="请求方法")
    request_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="请求路径")
    request_body: Mapped[dict] = mapped_column(JSON, nullable=True, comment="请求体")
    request_query: Mapped[dict] = mapped_column(JSON, nullable=True, comment="查询参数")

    # 执行结果
    result: Mapped[dict] = mapped_column(JSON, nullable=True, comment="执行结果")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误堆栈")

    # 节点执行详情
    node_executions: Mapped[dict] = mapped_column(JSON, nullable=True, comment="节点执行详情")

    workflow: Mapped["Workflow"] = relationship("Workflow")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "execution_id": self.execution_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "status": self.status,
            "final_node": self.final_node,
            "iterations": self.iterations,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "request_body": self.request_body,
            "request_query": self.request_query,
            "result": self.result,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "node_executions": self.node_executions,
        }
