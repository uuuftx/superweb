"""核心配置"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "SuperWeb"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/superweb.db"

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # UI配置
    UI_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
