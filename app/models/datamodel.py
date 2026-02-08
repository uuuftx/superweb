"""数据模型配置"""

from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class DataModel(Base):
    """数据模型定义"""
    __tablename__ = "data_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="模型名称")
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="数据库表名")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="模型描述")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    fields: Mapped[list["ModelField"]] = relationship(
        "ModelField",
        back_populates="model",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "table_name": self.table_name,
            "description": self.description,
            "enabled": self.enabled,
        }


class ModelField(Base):
    """模型字段定义"""
    __tablename__ = "model_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("data_models.id"), nullable=False, comment="模型ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="字段名")
    field_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="字段类型: string, integer, float, boolean, datetime, text"
    )
    length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="字符串长度")
    required: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必填")
    unique: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否唯一")
    primary_key: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否主键")
    default_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="默认值")
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="字段描述")

    model: Mapped["DataModel"] = relationship("DataModel", back_populates="fields")
