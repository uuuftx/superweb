"""端点执行器"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import json
import importlib
from typing import Any
from datetime import datetime
import uuid

from app.models.endpoint import Endpoint
from app.models.datamodel import DataModel
from app.core.database import async_session_maker


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
    if endpoint.logic_type == "simple":
        result = await _execute_simple(endpoint, context)
    elif endpoint.logic_type == "workflow":
        result = await _execute_workflow(endpoint, context)
    elif endpoint.logic_type == "crud":
        result = await _execute_crud(endpoint, context)
    elif endpoint.logic_type == "custom":
        result = await _execute_custom_code(endpoint, context)
    else:
        result = {"error": f"未知逻辑类型: {endpoint.logic_type}"}

    return result


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
        current_data = {
            "request": context.get("request"),
            "context": context
        }
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
            node_log = {
                "node_number": current_node_num,
                "node_name": node.name,
                "start_time": datetime.now().isoformat(),
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

                # 记录节点执行成功
                node_log.update({
                    "status": "success",
                    "end_time": datetime.now().isoformat(),
                    "next_node": node_result.get('next_node', 0),
                    "output": str(node_result.get('result', {}))[:500]  # 只保留前500字符
                })

            except Exception as e:
                import traceback
                error_msg = str(e)
                error_tb = traceback.format_exc()

                # 记录节点执行失败
                node_log.update({
                    "status": "error",
                    "end_time": datetime.now().isoformat(),
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


async def save_execution_log(log_data):
    """保存执行日志到文件系统"""
    import os
    import json
    from pathlib import Path

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
    from datetime import datetime

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


async def execute_python_workflow(node_map, context):
    """执行端点逻辑"""

    # 获取请求参数
    if endpoint.method in ["POST", "PUT", "PATCH"]:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    else:
        body = {}

    query_params = dict(request.query_params)
    headers = dict(request.headers)

    # 合并所有参数
    context = {
        "path": path_params,
        "query": query_params,
        "body": body,
        "headers": headers,
        "request": request,
    }

    # 根据逻辑类型执行
    if endpoint.logic_type == "simple":
        return await _execute_simple(endpoint, context)
    elif endpoint.logic_type == "workflow":
        return await _execute_workflow(endpoint, context)
    elif endpoint.logic_type == "crud":
        return await _execute_crud(endpoint, context)
    else:
        raise ValueError(f"未知的逻辑类型: {endpoint.logic_type}")


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

        # 构建节点映射 - 按节点编号索引
        node_map = {}
        for node in nodes:
            node_num = int(node.node_id.split('_')[1]) if node.node_id.startswith('node_') else int(node.position_x / 200)
            node_map[node_num] = node

        # 从节点1开始执行
        try:
            result = await execute_python_workflow(node_map, context)
            return result
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}


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
    current_data = {
        "request": context.get("request"),
        "context": context
    }
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
    node_num = int(node.node_id.split('_')[1]) if node.node_id.startswith('node_') else int(node.position_x / 200)

    # 准备执行环境 - 直接执行，不使用沙箱
    exec_globals = {
        # Python 内置函数和模块
        "__builtins__": {
            # 基础类型和函数
            "print": print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
            "tuple": tuple,
            "set": set,
            "frozenset": frozenset,
            "bytearray": bytearray,
            "bytes": bytes,
            "memoryview": memoryview,
            # 函数
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "any": any,
            "all": all,
            "max": max,
            "min": min,
            "sum": sum,
            "abs": abs,
            "round": round,
            "divmod": divmod,
            "pow": pow,
            "hash": hash,
            "ord": ord,
            "chr": chr,
            "bin": bin,
            "hex": hex,
            "oct": oct,
            "bool": bool,
            "complex": complex,
            "float": float,
            "int": int,
            "str": str,
            "list": list,
            "tuple": tuple,
            "dict": dict,
            "set": set,
            "frozenset": frozenset,
            # 常用模块
            "json": json,
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
            # 数据处理
            "Counter": __import__("collections").Counter,
            "defaultdict": __import__("collections").defaultdict,
            "OrderedDict": __import__("collections").OrderedDict,
            "deque": __import__("collections").deque,
            # import 支持和更多常用库
            "__import__": __import__,
            "ImportError": ImportError,
            # 文件和路径
            "os": __import__("os"),
            "sys": __import__("sys"),
            "pathlib": __import__("pathlib"),
            "Path": __import__("pathlib").Path,
            # 字符串和文本
            "string": __import__("string"),
            "textwrap": __import__("textwrap"),
            # 数据处理
            "copy": __import__("copy"),
            "decimal": __import__("decimal"),
            "Decimal": __import__("decimal").Decimal,
            "fractions": __import__("fractions"),
            "Fraction": __import__("fractions").Fraction,
            # 数据统计
            "statistics": __import__("statistics"),
            # 序列化
            "pickle": __import__("pickle"),
            # 网络相关
            "urllib": __import__("urllib"),
            "urllib.parse": __import__("urllib.parse"),
            # HTML/XML
            "html": __import__("html"),
            "xml": __import__("xml"),
            # 数据库
            "sqlite3": __import__("sqlite3"),
            # 日志
            "logging": __import__("logging"),
            # 类型提示
            "typing": __import__("typing"),
            # 数据类
            "dataclasses": __import__("dataclasses"),
            # 枚举
            "enum": __import__("enum"),
            # 数字抽象
            "numbers": __import__("numbers"),
            # IP地址
            "ipaddress": __import__("ipaddress"),
            # 日期时间增强
            "dateutil": __import__("dateutil") if __import__("importlib").util.find_spec("dateutil") else None,
            # HTTP客户端
            "httpx": __import__("httpx") if __import__("importlib").util.find_spec("httpx") else None,
            # 环境变量
            "environ": __import__("os").environ,
        },
        # 上下文变量
        "request": context.get("request"),
        "data": data,
        "context": context,
        # 当前节点信息
        "node": node_num,
        "node_name": node.name,
        # 工具模块
        "datetime": __import__("datetime"),
        "time": __import__("time"),
        "uuid": __import__("uuid"),
        "json": json,
        "re": __import__("re"),
        "hashlib": __import__("hashlib"),
        "base64": __import__("base64"),
        "math": __import__("math"),
        "random": __import__("random"),
    }

    # 执行代码
    exec(code, exec_globals)

    # 获取返回值
    next_node = exec_globals.get('next_node', 0)
    result_data = exec_globals.get('result', data)
    result = exec_globals.get('response', result_data)

    return {
        "next_node": next_node,
        "data": result,
        "node": node_num
    }


async def execute_workflow_graph(start_node, node_map, graph, context):
    """
    执行工作流图

    Args:
        start_node: 开始节点
        node_map: 节点ID到节点的映射
        graph: 邻接表 {node_id: [next_node_ids]}
        context: 请求上下文
    """

    # 当前数据
    current_data = {
        "request": context,
        "context": context
    }

    # 执行栈，用于深度优先遍历
    # 格式: [(node_id, data)]
    stack = [(start_node.node_id, current_data)]

    # 已访问节点，防止循环
    visited = set()

    # 执行结果
    final_result = None

    while stack:
        node_id, data = stack.pop(0)

        if node_id in visited:
            continue

        visited.add(node_id)
        node = node_map.get(node_id)

        if not node:
            continue

        # 执行节点
        node_result = await execute_node(node, data, context)

        # 如果是 end 节点，保存最终结果
        if node.node_type == 'end':
            final_result = node_result

        # 获取下一个节点
        next_nodes = graph.get(node_id, [])

        if not next_nodes:
            continue

        if node.node_type == 'branch':
            # 分支节点：根据条件选择路径
            condition_result = node_result.get('condition_result', False)

            # 找到 true 和 false 分支
            # 这里假设分支后面连接两个节点，第一个是 true，第二个是 false
            # 或者根据节点名称/配置来判断
            if condition_result and len(next_nodes) > 0:
                stack.append((next_nodes[0], node_result.get('data', node_result)))
            elif not condition_result and len(next_nodes) > 1:
                stack.append((next_nodes[1], node_result.get('data', node_result)))
            else:
                # 默认行为
                for next_node in next_nodes:
                    stack.append((next_node, node_result.get('data', node_result)))
        elif node.node_type == 'parallel':
            # 并行节点：并行执行所有下游节点
            results = []
            for next_node in next_nodes:
                results.append(await execute_workflow_from_node(
                    next_node, node_map, graph,
                    node_result.get('data', node_result),
                    context, visited.copy()
                ))
            node_result['parallel_results'] = results
        else:
            # 普通节点：依次处理所有下游节点
            for next_node in next_nodes:
                stack.append((next_node, node_result.get('data', node_result)))

    return final_result or {"message": "Workflow executed", "data": current_data}


async def execute_workflow_from_node(node_id, node_map, graph, data, context, visited):
    """从指定节点开始执行工作流（用于并行执行）"""
    stack = [(node_id, data)]
    result = None

    while stack:
        current_id, current_data = stack.pop(0)

        if current_id in visited:
            continue

        visited.add(current_id)
        node = node_map.get(current_id)

        if not node:
            continue

        node_result = await execute_node(node, current_data, context)

        if node.node_type == 'end':
            result = node_result
            break

        next_nodes = graph.get(current_id, [])
        for next_node in next_nodes:
            stack.append((next_node, node_result.get('data', node_result)))

    return result


async def execute_node(node, data, context):
    """
    执行单个节点

    Args:
        node: 工作流节点
        data: 输入数据
        context: 请求上下文

    Returns:
        节点执行结果
    """
    node_type = node.node_type
    config = node.config or {}

    if node_type == 'start':
        # 请求接收节点
        return {
            "data": {
                "path": context.get("path", {}),
                "query": context.get("query", {}),
                "headers": context.get("headers", {}),
                "body": context.get("body", {}),
                "request": context.get("request")
            },
            "message": "请求已接收"
        }

    elif node_type == 'end':
        # 响应返回节点
        status_code = config.get('status_code', 200)
        body_template = config.get('body_template', '{}')

        # 渲染响应模板
        try:
            response_data = data
            if isinstance(body_template, str):
                # 使用 JSON 模板
                template_json = json.loads(body_template)
                response_data = _render_template(template_json, {"data": data, "context": context})
            else:
                response_data = body_template
        except:
            response_data = data

        return {
            "status_code": status_code,
            "data": response_data,
            "headers": config.get('headers', {})
        }

    elif node_type == 'branch':
        # 分支判断节点
        condition = config.get('condition', 'True')

        # 准备执行环境
        exec_globals = {
            "data": data,
            "request": context.get("request"),
            "context": context,
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
            }
        }

        # 执行条件判断
        try:
            exec(f"_condition_result = {condition}", exec_globals)
            condition_result = exec_globals.get("_condition_result", False)
        except Exception as e:
            condition_result = False

        return {
            "condition_result": condition_result,
            "data": data
        }

    elif node_type == 'parallel':
        # 并行执行节点
        return {
            "data": data,
            "parallel": True
        }

    elif node_type == 'python':
        # Python 脚本节点
        code = config.get('code', '')

        # 准备执行环境
        exec_globals = {
            "data": data,
            "request": context.get("request"),
            "context": context,
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "dict": dict,
                "list": list,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "sum": sum,
                "max": max,
                "min": min,
                "abs": abs,
                "round": round,
                "json": json,
                "datetime": __import__("datetime"),
                "uuid": __import__("uuid"),
                "re": __import__("re"),
                "hashlib": __import__("hashlib"),
                "base64": __import__("base64"),
                "time": __import__("time"),
            }
        }

        # 执行 Python 代码
        try:
            exec(code, exec_globals)
            result = exec_globals.get("result", data)
        except Exception as e:
            raise RuntimeError(f"Python 节点执行错误 ({node.name}): {str(e)}")

        return {
            "data": result,
            "message": f"Python 脚本执行完成"
        }

    elif node_type == 'transform':
        # 数据转换节点
        transform_type = config.get('transform_type', 'map')

        if transform_type == 'map':
            mapping = config.get('mapping', {})
            result = data
            if isinstance(data, dict):
                for old_key, new_key in mapping.items():
                    if old_key in data:
                        result[new_key] = data[old_key]

        elif transform_type == 'template':
            template = config.get('template', '')
            result = _render_template(template, {"data": data})

        return {
            "data": result,
            "transformed": True
        }

    elif node_type == 'validate':
        # 数据验证节点
        schema = config.get('schema', '{}')
        rules = config.get('rules', [])

        try:
            schema_dict = json.loads(schema) if isinstance(schema, str) else schema
        except:
            schema_dict = {}

        # 简单验证：检查必填字段
        is_valid = True
        errors = []

        if isinstance(data, dict):
            for field, required in schema_dict.items():
                if required and field not in data:
                    is_valid = False
                    errors.append(f"缺少必填字段: {field}")

        return {
            "data": data if is_valid else {"validation_errors": errors},
            "valid": is_valid
        }

    elif node_type == 'database':
        # 数据库操作节点
        operation = config.get('operation', 'query')
        table_name = config.get('table', '')

        if not table_name:
            raise ValueError("数据库节点需要指定 table_name")

        from app.core.database import engine
        from sqlalchemy import Table, MetaData, select, insert, update, delete, text

        metadata = MetaData()

        async with engine.begin() as conn:
            table = Table(table_name, metadata, autoload_with=conn)

            if operation == 'query' or operation == 'get':
                # 查询操作
                if isinstance(data, dict) and 'id' in data:
                    stmt = select(table).where(table.c.id == data['id'])
                    result = await conn.execute(stmt)
                    row = result.fetchone()
                    result_data = {col.name: getattr(row, col.name) for col in table.columns} if row else None
                else:
                    stmt = select(table)
                    result = await conn.execute(stmt)
                    rows = result.fetchall()
                    result_data = [{col.name: getattr(row, col.name) for col in table.columns} for row in rows]

            elif operation == 'insert' or operation == 'create':
                # 插入操作
                if 'id' in data:
                    del data['id']  # 让数据库自动生成 ID
                stmt = insert(table).values(**data).returning(table.c.id)
                result = await conn.execute(stmt)
                result_data = {"id": result.scalar()}

            elif operation == 'update' or operation == 'set':
                # 更新操作
                if 'id' not in data:
                    raise ValueError("更新操作需要提供 id")
                stmt = update(table).where(table.c.id == data['id']).values(**{k: v for k, v in data.items() if k != 'id'})
                await conn.execute(stmt)
                result_data = {"updated": True}

            elif operation == 'delete':
                # 删除操作
                if 'id' not in data:
                    raise ValueError("删除操作需要提供 id")
                stmt = delete(table).where(table.c.id == data['id'])
                await conn.execute(stmt)
                result_data = {"deleted": True}

            else:
                # 自定义查询
                query = config.get('query', '')
                if query:
                    stmt = text(query)
                    result = await conn.execute(stmt)
                    result_data = result.fetchall()
                else:
                    result_data = data

        return {
            "data": result_data,
            "operation": operation
        }

    elif node_type == 'cache':
        # 缓存操作节点
        operation = config.get('operation', 'get')
        key = data.get('key', '')
        value = data.get('value', None)

        # 简单的内存缓存（生产环境应使用 Redis）
        if not hasattr(execute_workflow, '_cache'):
            execute_workflow._cache = {}

        cache = execute_workflow._cache

        if operation == 'get':
            result = cache.get(key)
        elif operation == 'set':
            cache[key] = value
            ttl = config.get('ttl', 3600)
            result = {"cached": True, "key": key}
        elif operation == 'delete':
            if key in cache:
                del cache[key]
            result = {"deleted": True}
        else:
            result = data

        return {
            "data": result
        }

    elif node_type == 'http':
        # HTTP 请求节点
        import httpx

        url = config.get('url', '')
        method = config.get('method', 'GET')
        headers = config.get('headers', {})
        body = config.get('body', {})

        async with httpx.AsyncClient() as client:
            if method.upper() == 'GET':
                response = await client.get(url, params=data.get('params', data), headers=headers)
            elif method.upper() == 'POST':
                response = await client.post(url, json=body or data, headers=headers)
            elif method.upper() == 'PUT':
                response = await client.put(url, json=body or data, headers=headers)
            elif method.upper() == 'DELETE':
                response = await client.delete(url, headers=headers)
            else:
                response = await client.get(url, headers=headers)

            try:
                result = response.json()
            except:
                result = {"text": response.text}

        return {
            "data": result,
            "status_code": response.status_code
        }

    elif node_type == 'webhook':
        # Webhook 节点
        import httpx

        url = config.get('url', '')
        method = config.get('method', 'POST')
        headers = config.get('headers', {})

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, json=data, headers=headers)
            try:
                result = response.json()
            except:
                result = {"text": response.text}

        return {
            "data": result,
            "status_code": response.status_code
        }

    else:
        # 未知节点类型
        return {
            "data": data,
            "message": f"节点类型 {node_type} 未处理"
        }


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


async def _crud_get_one(session: AsyncSession, model: DataModel, item_id: int) -> dict:
    """获取单条记录"""
    # 动态创建表连接
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
