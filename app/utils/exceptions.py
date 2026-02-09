"""自定义异常类"""


class SuperWebException(Exception):
    """基础异常类"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class WorkflowException(SuperWebException):
    """工作流相关异常"""
    pass


class NodeExecutionException(SuperWebException):
    """节点执行异常"""
    pass


class DatabaseConfigException(SuperWebException):
    """数据库配置异常"""
    pass


class ValidationException(SuperWebException):
    """验证异常"""
    pass


class ResourceNotFoundException(SuperWebException):
    """资源未找到异常"""
    pass
