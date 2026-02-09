"""端点执行器

优化说明：
1. 缓存模块导入和执行环境，避免每次执行都重新导入
2. 移除未使用的图形工作流相关代码
3. 修复重复代码和错误处理
4. 添加节点执行时长记录
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import json
import importlib
from typing import Any
from datetime import datetime
import uuid
from functools import lru_cache
from pathlib import Path

from app.models.endpoint import Endpoint
from app.models.datamodel import DataModel
from app.core.database import async_session_maker


# ==================== 执行环境缓存 ====================

@lru_cache(maxsize=1)
def _get_cached_modules():
    """缓存常用模块导入，避免每次执行都重新导入"""
    return {
        "os": __import__("os"),
        "sys": __import__("sys"),
        "datetime": __import__("datetime"),
        "time": __import__("time"),
        "uuid": __import__("uuid"),
        "random": __import__("random"),
        "re": __import__("re"),
        "hashlib": __import__("hashlib"),
        "base64": __import__("base64"),
        "math": __import__("math"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "functools": __import__("functools"),
        "typing": __import__("typing"),
        "copy": __import__("copy"),
        "decimal": __import__("decimal"),
        "statistics": __import__("statistics"),
        "pickle": __import__("pickle"),
        "urllib": __import__("urllib"),
        "html": __import__("html"),
        "xml": __import__("xml"),
        "sqlite3": __import__("sqlite3"),
        "logging": __import__("logging"),
        "dataclasses": __import__("dataclasses"),
        "enum": __import__("enum"),
        "numbers": __import__("numbers"),
        "ipaddress": __import__("ipaddress"),
        "pathlib": __import__("pathlib"),
        "string": __import__("string"),
        "textwrap": __import__("textwrap"),
        "fractions": __import__("fractions"),
    }


@lru_cache(maxsize=1)
def _get_optional_modules():
    """缓存可选模块导入"""
    modules = {"dateutil": None, "httpx": None}
    for name in modules:
        try:
            if importlib.util.find_spec(name):
                modules[name] = __import__(name)
        except:
            pass
    return modules


def _create_execution_globals(data, context, node_num, node_name):
    """创建 Python 代码执行的全局变量环境"""
    cached_modules = _get_cached_modules()
    optional_modules = _get_optional_modules()

    _os = cached_modules["os"]
    _sys = cached_modules["sys"]
    _datetime = cached_modules["datetime"]
    _time = cached_modules["time"]
    _uuid = cached_modules["uuid"]
    _random = cached_modules["random"]
    _re = cached_modules["re"]
    _hashlib = cached_modules["hashlib"]
    _base64 = cached_modules["base64"]
    _math = cached_modules["math"]
    _collections = cached_modules["collections"]
    _itertools = cached_modules["itertools"]
    _functools = cached_modules["functools"]
    _typing = cached_modules["typing"]
    _copy = cached_modules["copy"]
    _decimal = cached_modules["decimal"]
    _statistics = cached_modules["statistics"]
    _pickle = cached_modules["pickle"]
    _urllib = cached_modules["urllib"]
    _html = cached_modules["html"]
    _xml = cached_modules["xml"]
    _sqlite3 = cached_modules["sqlite3"]
    _logging = cached_modules["logging"]
    _dataclasses = cached_modules["dataclasses"]
    _enum = cached_modules["enum"]
    _numbers = cached_modules["numbers"]
    _ipaddress = cached_modules["ipaddress"]
    _pathlib = cached_modules["pathlib"]
    _string = cached_modules["string"]
    _textwrap = cached_modules["textwrap"]
    _fractions = cached_modules["fractions"]

    return {
        "__builtins__": {
            # 基础类型和函数
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "dict": dict, "list": list, "tuple": tuple, "set": set,
            "frozenset": frozenset, "bytearray": bytearray, "bytes": bytes, "memoryview": memoryview,
            # 函数
            "range": range, "enumerate": enumerate, "zip": zip, "map": map,
            "filter": filter, "sorted": sorted, "reversed": reversed,
            "any": any, "all": all, "max": max, "min": min, "sum": sum,
            "abs": abs, "round": round, "divmod": divmod, "pow": pow,
            "hash": hash, "ord": ord, "chr": chr, "bin": bin, "hex": hex,
            "oct": oct, "complex": complex,
            # 常用模块
            "json": json, "datetime": _datetime, "time": _time, "uuid": _uuid,
            "random": _random, "re": _re, "hashlib": _hashlib, "base64": _base64,
            "math": _math, "collections": _collections, "itertools": _itertools,
            "functools": _functools, "typing": _typing,
            # 数据处理
            "Counter": _collections.Counter, "defaultdict": _collections.defaultdict,
            "OrderedDict": _collections.OrderedDict, "deque": _collections.deque,
            # import 支持
            "__import__": __import__, "ImportError": ImportError,
            # 文件和路径
            "os": _os, "sys": _sys, "pathlib": _pathlib, "Path": _pathlib.Path,
            # 字符串和文本
            "string": _string, "textwrap": _textwrap,
            # 数据处理
            "copy": _copy, "decimal": _decimal, "Decimal": _decimal.Decimal,
            "fractions": _fractions, "Fraction": _fractions.Fraction,
            # 数据统计
            "statistics": _statistics,
            # 序列化
            "pickle": _pickle,
            # 网络相关
            "urllib": _urllib,
            # HTML/XML
            "html": _html, "xml": _xml,
            # 数据库
            "sqlite3": _sqlite3,
            # 日志
            "logging": _logging,
            # 数据类
            "dataclasses": _dataclasses,
            # 枚举
            "enum": _enum,
            # 数字抽象
            "numbers": _numbers,
            # IP地址
            "ipaddress": _ipaddress,
            # 可选模块
            "dateutil": optional_modules["dateutil"],
            "httpx": optional_modules["httpx"],
            # 环境变量
            "environ": _os.environ,
        },
        # 上下文变量
        "request": context.get("request"),
        "data": data,
        "context": context,
        # 当前节点信息
        "node": node_num,
        "node_name": node_name,
        # 工具模块（顶层访问）
        "datetime": _datetime, "time": _time, "uuid": _uuid, "json": json,
        "re": _re, "hashlib": _hashlib, "base64": _base64, "math": _math, "random": _random,
    }


# ==================== 端点执行 ====================

async def execute_endpoint(endpoint: Endpoint, request: Request, path_params: dict = None):
    """
    执行端点逻辑

    Args:
        endpoint: 端点对象
        request: FastAPI请求对象
        path_params: 路径参数

    Returns:
        执行结果
    """
    from fastapi.responses import JSONResponse

    # 获取请求参数
    query_params = dict(request.query_params)

    # 获取请求体
    try:
        body = await request.json()
    except:
        body = {}

    # 构建上下文
    context = {
        "path": path_params or {},
        "query": query_params,
        "body": body,
        "headers": dict(request.headers),
        "request": request,
    }

    # 根据逻辑类型执行
    dispatch_map = {
        "simple": _execute_simple,
        "workflow": _execute_workflow,
        "crud": _execute_crud,
        "custom": _execute_custom_code,
    }

    executor = dispatch_map.get(endpoint.logic_type)
    if executor:
        result = await executor(endpoint, context)
    else:
        result = {"error": f"未知逻辑类型: {endpoint.logic_type}"}

    return result


# ==================== 工作流执行 ====================

async def execute_python_workflow_with_logging(node_map, context, workflow_id, workflow_name, enable_logging=True):
    """
    执行Python脚本工作流（带日志记录）

    Args:
        node_map: 节点映射 {node_number: node}
        context: 请求上下文
        workflow_id: 工作流ID
        workflow_name: 工作流名称
        enable_logging: 是否启用日志

    Returns:
        执行结果字典
    """
    execution_id = str(uuid.uuid4())
    start_time = datetime.now()

    # 初始化日志记录
    execution_log = {
        "execution_id": execution_id,
        "start_time": start_time,
        "status": "running",
        "node_executions": [],
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "request_method": context.get("body", {}).get("_method", "POST"),
        "request_path": f"/workflow/api/{workflow_name}",
        "request_query": context.get("query", {}),
    }

    try:
        # 执行工作流
        current_node_num = 1
        current_data = {}
        visited = set()
        max_iterations = 1000
        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            if current_node_num not in node_map:
                result = {
                    "message": f"工作流结束：节点 {current_node_num} 不存在",
                    "final_node": current_node_num - 1,
                    "data": current_data
                }
                break

            if current_node_num in visited:
                result = {
                    "error": f"检测到循环：节点 {current_node_num} 已访问",
                    "current_node": current_node_num,
                    "data": current_data
                }
                break

            visited.add(current_node_num)
            node = node_map[current_node_num]

            # 记录节点执行开始
            node_start_time = datetime.now()
            node_log = {
                "node_number": current_node_num,
                "node_name": node.name,
                "start_time": node_start_time.isoformat(),
            }

            # 执行节点
            code = node.config.get('code', '')
            if not code:
                result = {
                    "error": f"节点 {current_node_num} 没有代码",
                    "node": current_node_num
                }
                break

            try:
                node_result = await execute_python_node(node, current_data, context)

                # 计算节点执行时长
                node_end_time = datetime.now()
                node_duration = (node_end_time - node_start_time).total_seconds()

                # 记录节点执行成功
                node_log.update({
                    "status": "success",
                    "end_time": node_end_time.isoformat(),
                    "duration": node_duration,
                    "next_node": node_result.get('next_node', 0),
                    "output": str(node_result.get('result', {}))[:500]  # 只保留前500字符
                })

            except Exception as e:
                import traceback
                error_msg = str(e)
                error_tb = traceback.format_exc()

                # 计算节点执行时长
                node_end_time = datetime.now()
                node_duration = (node_end_time - node_start_time).total_seconds()

                # 记录节点执行失败
                node_log.update({
                    "status": "error",
                    "end_time": node_end_time.isoformat(),
                    "duration": node_duration,
                    "error": error_msg,
                    "traceback": error_tb
                })

                result = {
                    "error": f"节点 {current_node_num} 执行失败: {error_msg}",
                    "node": current_node_num,
                    "traceback": error_tb
                }
                break

            execution_log["node_executions"].append(node_log)

            # 获取下一个节点
            next_node = node_result.get('next_node', 0)
            current_data = node_result.get('data', current_data)

            if next_node <= 0 or next_node not in node_map:
                result = {
                    "message": "工作流执行完成",
                    "final_node": current_node_num,
                    "data": current_data,
                    "iterations": iterations
                }
                break

            current_node_num = next_node

        # 记录结束信息
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        execution_log.update({
            "end_time": end_time,
            "duration": duration,
            "status": "error" if "error" in result else "success",
            "final_node": result.get("final_node"),
            "iterations": iterations,
            "result": result
        })

        if "error" in result:
            execution_log["error_message"] = result.get("error")
            execution_log["error_traceback"] = result.get("traceback")

        # 如果启用日志，保存到文件
        if enable_logging:
            await save_execution_log(execution_log)

        # 在结果中添加execution_id
        result["execution_id"] = execution_id

        return result

    except Exception as e:
        import traceback
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        execution_log.update({
            "end_time": end_time,
            "duration": duration,
            "status": "error",
            "error_message": str(e),
            "error_traceback": traceback.format_exc(),
            "result": {"error": str(e)}
        })

        if enable_logging:
            await save_execution_log(execution_log)

        # 返回错误信息和execution_id
        error_result = {
            "error": str(e),
            "execution_id": execution_id
        }

        return error_result


async def execute_python_workflow(node_map, context):
    """
    执行 Python 脚本工作流

    Args:
        node_map: {node_number: node} 节点编号到节点的映射
        context: 请求上下文

    Returns:
        最终执行结果
    """
    current_node_num = 1
    current_data = {}
    visited = set()
    max_iterations = 1000  # 防止无限循环
    iterations = 0

    while iterations < max_iterations:
        iterations += 1

        # 检查节点是否存在
        if current_node_num not in node_map:
            return {
                "message": f"工作流结束：节点 {current_node_num} 不存在",
                "final_node": current_node_num - 1,
                "data": current_data
            }

        # 检查循环
        if current_node_num in visited:
            return {
                "error": f"检测到循环：节点 {current_node_num} 已访问",
                "current_node": current_node_num,
                "data": current_data
            }

        visited.add(current_node_num)
        node = node_map[current_node_num]

        # 获取节点代码
        code = node.config.get('code', '')
        if not code:
            return {
                "error": f"节点 {current_node_num} 没有代码",
                "node": current_node_num
            }

        # 执行 Python 脚本
        try:
            result = await execute_python_node(node, current_data, context)
        except Exception as e:
            import traceback
            return {
                "error": f"节点 {current_node_num} 执行失败: {str(e)}",
                "node": current_node_num,
                "traceback": traceback.format_exc()
            }

        # 从结果中获取下一个节点和数据
        next_node = result.get('next_node', 0)
        current_data = result.get('data', current_data)

        # 如果 next_node 是 0 或不存在，结束流程
        if next_node <= 0 or next_node not in node_map:
            return {
                "message": "工作流执行完成",
                "final_node": current_node_num,
                "data": current_data,
                "iterations": iterations
            }

        # 继续执行下一个节点
        current_node_num = next_node

    return {
        "error": "工作流超过最大迭代次数",
        "iterations": iterations
    }


async def execute_python_node(node, data, context):
    """
    执行 Python 节点

    Args:
        node: 工作流节点
        data: 输入数据
        context: 请求上下文

    Returns:
        执行结果 {next_node: int, data: dict}
    """
    code = node.config.get('code', '')
    node_num = int(node.position_x / 200)

    # 创建执行环境（使用缓存的模块）
    exec_globals = _create_execution_globals(data, context, node_num, node.name)

    # 注入激活的数据库连接
    from app.core.database import get_all_active_db_configs
    try:
        active_dbs = await get_all_active_db_configs()
        for db_name, db_info in active_dbs.items():
            # 获取session maker，注入一个便捷的获取连接的方法
            session_maker = db_info["session_maker"]
            if session_maker:
                # 创建一个便捷的连接获取对象
                class DBConnection:
                    def __init__(self, session_maker):
                        self._session_maker = session_maker

                    async def acquire(self):
                        """获取数据库连接"""
                        return self._session_maker()

                    async def execute(self, query, params=None):
                        """便捷的执行方法"""
                        async with self._session_maker() as session:
                            from sqlalchemy import text
                            stmt = text(query)
                            if params:
                                stmt = stmt.bindparams(**params)
                            result = await session.execute(stmt)
                            await session.commit()  # 显式提交
                            # 尝试获取所有行，如果不返回行则返回受影响的行数
                            try:
                                return result.fetchall()
                            except:
                                # INSERT/UPDATE/DELETE 等不返回行的语句
                                return result.rowcount

                exec_globals[db_name] = DBConnection(session_maker)

                # 如果是默认配置，额外注入为 'db'
                if db_info["config"].is_default:
                    exec_globals["db"] = DBConnection(session_maker)
    except Exception as e:
        # 数据库连接注入失败不影响脚本执行
        import logging
        logging.warning(f"数据库连接注入失败: {e}")

    # 检测是否包含异步代码
    is_async = any(keyword in code for keyword in ['async ', 'await ', 'async with'])

    if is_async:
        # 将代码包装为异步函数并执行
        lines = []
        for line in code.split('\n'):
            if line.strip():  # 非空行添加缩进
                lines.append('    ' + line)
            else:  # 空行保持原样
                lines.append(line)

        indented_code = '\n'.join(lines)

        # 包装成异步函数
        wrapped_code = (
            'async def _execute_async_node(data, context, node, node_name):\n'
            + indented_code + '\n'
            + '    # 返回关键变量\n'
            + '    _result = {}\n'
            + '    try:\n'
            + '        _result["next_node"] = next_node\n'
            + '    except:\n'
            + '        _result["next_node"] = 0\n'
            + '    try:\n'
            + '        _result["result"] = result\n'
            + '    except:\n'
            + '        pass\n'
            + '    try:\n'
            + '        _result["response"] = response\n'
            + '    except:\n'
            + '        pass\n'
            + '    try:\n'
            + '        _result["data"] = data\n'
            + '    except:\n'
            + '        pass\n'
            + '    return _result\n'
        )

        # 编译并执行包装后的代码
        exec(wrapped_code, exec_globals)

        # 获取异步函数并执行
        async_func = exec_globals.get('_execute_async_node')
        if async_func:
            async_locals = await async_func(data, context, None, node.name)
            # 将返回的变量合并到全局变量
            for key, value in async_locals.items():
                if value is not None and key != 'data':  # 避免覆盖输入的 data
                    exec_globals[key] = value
    else:
        # 执行同步代码
        exec(code, exec_globals)

    # 获取返回值
    next_node = exec_globals.get('next_node', 0)
    # 获取返回数据，优先级: response > result > data(来自exec_globals)
    result_data = exec_globals.get('response') or exec_globals.get('result') or exec_globals.get('data') or data

    return {
        "next_node": next_node,
        "data": result_data,
        "node": node_num
    }


# ==================== 日志处理 ====================

async def save_execution_log(log_data):
    """保存执行日志到文件系统"""
    # 创建日志目录
    log_dir = Path("storage/workflow_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名：时间_UUID.log
    start_time = log_data["start_time"]
    execution_id = log_data["execution_id"]

    # 格式化时间：YYYYMMDD_HHMMSS
    time_str = start_time.strftime("%Y%m%d_%H%M%S")

    # 创建安全文件名（移除UUID中的连字符）
    safe_id = execution_id.replace("-", "")
    filename = f"{time_str}_{safe_id}.log"
    filepath = log_dir / filename

    # 格式化日志内容为可读文本
    log_content = format_execution_log(log_data)

    # 写入文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(log_content)

    return filepath


def format_execution_log(log_data):
    """格式化执行日志为可读文本"""
    lines = []
    lines.append("=" * 80)
    lines.append("工作流执行日志")
    lines.append("=" * 80)
    lines.append("")

    # 基本信息
    lines.append("【基本信息】")
    lines.append(f"  执行ID:     {log_data.get('execution_id', 'N/A')}")
    lines.append(f"  工作流ID:   {log_data.get('workflow_id', 'N/A')}")
    lines.append(f"  工作流名称: {log_data.get('workflow_name', 'N/A')}")
    lines.append(f"  开始时间:   {log_data.get('start_time', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}")
    if log_data.get('end_time'):
        lines.append(f"  结束时间:   {log_data['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    if log_data.get('duration'):
        lines.append(f"  执行时长:   {log_data['duration']:.3f} 秒")
    lines.append(f"  状态:       {log_data.get('status', 'unknown').upper()}")
    if log_data.get('final_node'):
        lines.append(f"  最终节点:   {log_data['final_node']}")
    if log_data.get('iterations'):
        lines.append(f"  迭代次数:   {log_data['iterations']}")
    lines.append("")

    # 请求信息
    lines.append("【请求信息】")
    lines.append(f"  请求方法:   {log_data.get('request_method', 'POST')}")
    lines.append(f"  请求路径:   {log_data.get('request_path', 'N/A')}")
    if log_data.get('request_query'):
        lines.append(f"  查询参数:")
        for key, value in log_data['request_query'].items():
            lines.append(f"    {key}: {value}")
    if log_data.get('request_body'):
        lines.append(f"  请求体:")
        try:
            body_str = json.dumps(log_data['request_body'], ensure_ascii=False, indent=2)
            for line in body_str.split('\n'):
                lines.append(f"    {line}")
        except:
            lines.append(f"    {log_data['request_body']}")
    lines.append("")

    # 节点执行详情
    if log_data.get('node_executions'):
        lines.append("【节点执行详情】")
        for i, node_exec in enumerate(log_data['node_executions'], 1):
            lines.append(f"  节点 {i}: {node_exec.get('node_name', 'Unknown')}")
            lines.append(f"    编号:     {node_exec.get('node_number', 'N/A')}")
            lines.append(f"    开始时间: {node_exec.get('start_time', 'N/A')}")
            if node_exec.get('end_time'):
                lines.append(f"    结束时间: {node_exec.get('end_time')}")
            if node_exec.get('duration'):
                lines.append(f"    耗时:     {node_exec['duration']:.3f}秒")
            lines.append(f"    状态:     {node_exec.get('status', 'unknown').upper()}")

            if node_exec.get('input_data'):
                lines.append(f"    输入数据:")
                try:
                    input_str = json.dumps(node_exec['input_data'], ensure_ascii=False, indent=2)
                    for line in input_str.split('\n'):
                        lines.append(f"      {line}")
                except:
                    lines.append(f"      {node_exec['input_data']}")

            if node_exec.get('output_data'):
                lines.append(f"    输出数据:")
                try:
                    output_str = json.dumps(node_exec['output_data'], ensure_ascii=False, indent=2)
                    for line in output_str.split('\n'):
                        lines.append(f"      {line}")
                except:
                    lines.append(f"      {node_exec['output_data']}")

            if node_exec.get('error'):
                lines.append(f"    错误:     {node_exec['error']}")

            lines.append("")

    # 执行结果
    if log_data.get('result'):
        lines.append("【执行结果】")
        try:
            result_str = json.dumps(log_data['result'], ensure_ascii=False, indent=2)
            for line in result_str.split('\n'):
                lines.append(f"  {line}")
        except:
            lines.append(f"  {log_data['result']}")
        lines.append("")

    # 错误信息
    if log_data.get('error_message'):
        lines.append("【错误信息】")
        lines.append(f"  {log_data['error_message']}")
        lines.append("")

    if log_data.get('error_traceback'):
        lines.append("【错误堆栈】")
        for line in log_data['error_traceback'].split('\n'):
            lines.append(f"  {line}")
        lines.append("")

    lines.append("=" * 80)
    lines.append(f"日志生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)

    return '\n'.join(lines)


# ==================== 端点逻辑执行器 ====================

async def _execute_simple(endpoint: Endpoint, context: dict) -> Any:
    """执行简单逻辑（自定义代码或固定响应）"""

    if endpoint.custom_code:
        # 执行自定义代码
        return await _execute_custom_code(endpoint, context)
    elif endpoint.response_template:
        # 返回固定模板
        try:
            template = json.loads(endpoint.response_template)
            return _render_template(template, context)
        except json.JSONDecodeError:
            return {"message": endpoint.response_template}
    else:
        return {"message": f"Endpoint {endpoint.name} executed"}


async def _execute_workflow(endpoint: Endpoint, context: dict) -> Any:
    """执行工作流 - 只支持 Python 脚本节点，通过节点编号跳转"""
    if not endpoint.workflow_id:
        raise ValueError("工作流端点必须关联 workflow_id")

    from app.core.database import async_session_maker
    from app.models.workflow import WorkflowNode

    async with async_session_maker() as session:
        # 获取所有节点
        nodes_result = await session.execute(
            select(WorkflowNode)
            .where(WorkflowNode.workflow_id == endpoint.workflow_id)
            .order_by(WorkflowNode.position_x)  # 按 position_x 排序（即节点编号）
        )
        nodes = nodes_result.scalars().all()

        if not nodes:
            return {"error": "工作流为空"}

        # 构建节点映射 - 按节点编号索引（从 position_x 计算）
        node_map = {}
        for node in nodes:
            node_num = int(node.position_x / 200)
            node_map[node_num] = node

        # 从节点1开始执行
        try:
            result = await execute_python_workflow(node_map, context)
            return result
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}


async def _execute_crud(endpoint: Endpoint, context: dict) -> Any:
    """执行数据库CRUD操作"""
    if not endpoint.model_id:
        raise ValueError("CRUD端点必须关联数据模型")

    async with async_session_maker() as session:
        # 获取模型信息
        model_result = await session.execute(
            select(DataModel).where(DataModel.id == endpoint.model_id)
        )
        model = model_result.scalar_one_or_none()

        if not model:
            raise ValueError(f"数据模型不存在: {endpoint.model_id}")

        # 根据方法执行不同操作
        if endpoint.method == "GET":
            if context.get("path", {}).get("id"):
                return await _crud_get_one(session, model, context["path"]["id"])
            else:
                return await _crud_get_list(session, model, context["query"])

        elif endpoint.method == "POST":
            return await _crud_create(session, model, context["body"])

        elif endpoint.method == "PUT":
            if not context.get("path", {}).get("id"):
                raise ValueError("PUT操作需要提供id")
            return await _crud_update(session, model, context["path"]["id"], context["body"])

        elif endpoint.method == "DELETE":
            if not context.get("path", {}).get("id"):
                raise ValueError("DELETE操作需要提供id")
            return await _crud_delete(session, model, context["path"]["id"])

        else:
            raise ValueError(f"不支持的CRUD方法: {endpoint.method}")


async def _execute_custom_code(endpoint: Endpoint, context: dict) -> Any:
    """执行自定义代码"""
    # 准备执行环境
    safe_globals = {
        "__builtins__": {
            "print": print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
            "json": json,
        },
        "context": context,
        "json": json,
    }

    try:
        # 执行代码
        exec(endpoint.custom_code, safe_globals)

        # 如果有返回值
        if "result" in safe_globals:
            return safe_globals["result"]

        return {"message": "代码执行成功"}
    except Exception as e:
        raise RuntimeError(f"代码执行错误: {str(e)}")


# ==================== CRUD 操作 ====================

async def _crud_get_one(session: AsyncSession, model: DataModel, item_id: int) -> dict:
    """获取单条记录"""
    from sqlalchemy import Table, MetaData, select

    metadata = MetaData()
    engine = session.bind

    # 反射表结构
    table = Table(model.table_name, metadata, autoload_with=engine)

    # 查询数据
    stmt = select(table).where(table.c.id == item_id)
    result = await session.execute(stmt)
    row = result.fetchone()

    if not row:
        return {"error": "记录不存在"}

    return {col.name: getattr(row, col.name) for col in table.columns}


async def _crud_get_list(session: AsyncSession, model: DataModel, params: dict) -> dict:
    """获取记录列表"""
    from sqlalchemy import Table, MetaData, select, func

    metadata = MetaData()
    engine = session.bind
    table = Table(model.table_name, metadata, autoload_with=engine)

    # 分页参数
    page = int(params.get("page", 1))
    page_size = int(params.get("page_size", 20))

    # 计算总数
    count_stmt = select(func.count()).select_from(table)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar()

    # 查询数据
    offset = (page - 1) * page_size
    stmt = select(table).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    rows = result.fetchall()

    items = [{col.name: getattr(row, col.name) for col in table.columns} for row in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def _crud_create(session: AsyncSession, model: DataModel, data: dict) -> dict:
    """创建记录"""
    from sqlalchemy import Table, MetaData, insert

    metadata = MetaData()
    engine = session.bind
    table = Table(model.table_name, metadata, autoload_with=engine)

    stmt = insert(table).values(**data).returning(table.c.id)
    result = await session.execute(stmt)
    new_id = result.scalar()

    return {"id": new_id, "message": "创建成功"}


async def _crud_update(session: AsyncSession, model: DataModel, item_id: int, data: dict) -> dict:
    """更新记录"""
    from sqlalchemy import Table, MetaData, update

    metadata = MetaData()
    engine = session.bind
    table = Table(model.table_name, metadata, autoload_with=engine)

    stmt = update(table).where(table.c.id == item_id).values(**data)
    await session.execute(stmt)

    return {"message": "更新成功"}


async def _crud_delete(session: AsyncSession, model: DataModel, item_id: int) -> dict:
    """删除记录"""
    from sqlalchemy import Table, MetaData, delete

    metadata = MetaData()
    engine = session.bind
    table = Table(model.table_name, metadata, autoload_with=engine)

    stmt = delete(table).where(table.c.id == item_id)
    await session.execute(stmt)

    return {"message": "删除成功"}


# ==================== 模板渲染 ====================

def _render_template(template: Any, context: dict) -> Any:
    """渲染模板（支持变量替换）"""
    if isinstance(template, str):
        # 简单的变量替换 {{variable}}
        import re

        def replace_var(match):
            var_path = match.group(1).strip()
            # 支持嵌套访问 context.query.name
            parts = var_path.split(".")
            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return ""
            return str(value) if value is not None else ""

        return re.sub(r"\{\{(.+?)\}\}", replace_var, template)

    elif isinstance(template, dict):
        return {k: _render_template(v, context) for k, v in template.items()}

    elif isinstance(template, list):
        return [_render_template(item, context) for item in template]

    return template
