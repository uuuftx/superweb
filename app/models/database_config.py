"""数据库连接配置模型"""

from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class DatabaseConfig(Base):
    """数据库连接配置"""
    __tablename__ = "database_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="配置名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="配置描述")

    # 数据库类型
    db_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="数据库类型: sqlite, postgresql, mysql, mssql, oracle"
    )

    # 连接配置
    host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="主机地址")
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="端口")
    database: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="数据库名")
    username: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="用户名")
    password: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="密码（加密存储）")
    # SQLite 使用文件路径
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="SQLite 文件路径")

    # 连接池配置
    pool_size: Mapped[int] = mapped_column(Integer, default=5, comment="连接池大小")
    max_overflow: Mapped[int] = mapped_column(Integer, default=10, comment="最大溢出连接数")
    pool_timeout: Mapped[int] = mapped_column(Integer, default=30, comment="连接超时（秒）")
    pool_recycle: Mapped[int] = mapped_column(Integer, default=3600, comment="连接回收时间（秒）")

    # 额外配置
    extra_config: Mapped[dict] = mapped_column(JSON, default={}, comment="额外配置参数")

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为默认配置")

    # 元数据
    created_at: Mapped[str] = mapped_column(String(50), comment="创建时间")
    updated_at: Mapped[str] = mapped_column(String(50), comment="更新时间")

    def to_dict(self, include_secrets=False) -> dict:
        """转换为字典"""
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "path": self.path,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "extra_config": self.extra_config,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        # 仅在包含敏感信息时返回密码
        if include_secrets:
            data["password"] = self.password

        return data

    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
        if self.db_type == "sqlite":
            # SQLite: sqlite:///path/to/db.sqlite
            return f"sqlite:///{self.path}"

        elif self.db_type == "postgresql":
            # PostgreSQL: postgresql://user:pass@host:port/dbname
            return (
                f"postgresql://{self.username}:{self.password}@"
                f"{self.host}:{self.port}/{self.database}"
            )

        elif self.db_type == "mysql":
            # MySQL: mysql+pymysql://user:pass@host:port/dbname
            return (
                f"mysql+pymysql://{self.username}:{self.password}@"
                f"{self.host}:{self.port}/{self.database}"
            )

        elif self.db_type == "mssql":
            # SQL Server: mssql+pymssql://user:pass@host:port/dbname
            return (
                f"mssql+pymssql://{self.username}:{self.password}@"
                f"{self.host}:{self.port}/{self.database}"
            )

        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}")
