"""请求日志记录器"""

import time
from collections import deque
from typing import Dict, Any
from datetime import datetime


class RequestLogger:
    """请求日志记录器 - 内存中存储最近的请求"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.logs: deque = deque(maxlen=max_size)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        client_ip: str = None,
        user_agent: str = None,
        query_params: Dict = None,
        path_params: Dict = None
    ):
        """记录请求"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "query_params": query_params,
            "path_params": path_params,
            "success": 200 <= status_code < 400
        }
        self.logs.append(log_entry)

    def get_recent_logs(self, limit: int = 50) -> list:
        """获取最近的日志"""
        return list(self.logs)[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.logs:
            return {
                "total_requests": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "by_method": {},
                "by_status": {}
            }

        total = len(self.logs)
        success_count = sum(1 for log in self.logs if log["success"])
        total_duration = sum(log["duration_ms"] for log in self.logs)

        # 按方法统计
        by_method = {}
        for log in self.logs:
            method = log["method"]
            by_method[method] = by_method.get(method, 0) + 1

        # 按状态码统计
        by_status = {}
        for log in self.logs:
            status = log["status_code"]
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_requests": total,
            "success_rate": round((success_count / total) * 100, 2),
            "avg_duration_ms": round(total_duration / total, 2),
            "by_method": by_method,
            "by_status": by_status
        }

    def clear(self):
        """清空日志"""
        self.logs.clear()


# 全局请求日志记录器
request_logger = RequestLogger(max_size=200)
