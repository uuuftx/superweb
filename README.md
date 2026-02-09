# SuperWeb

<div align="center">

**可视化API开发框架**

通过界面配置开发接口，让API开发更简单、更高效

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ 特性

### 🎨 可视化开发
- **工作流编辑器** - 拖拽式节点编辑，可视化配置业务逻辑
- **多主题支持** - 深色/亮色主题，Monokai/Dracula/Material 等编辑器主题
- **实时预览** - 即时查看节点连接关系和执行流程

### 🔧 强大功能
- **动态端点** - 通过数据库配置动态生成 API 端点
- **工作流引擎** - 支持 Python 代码节点，灵活编写业务逻辑
- **数据库连接** - 支持连接多种外部数据库
- **日志系统** - 完整的请求日志和工作流执行日志

### 🛠️ 开发工具
- **API 测试器** - 内置 Postman 风格的 API 测试工具
- **请求日志** - 实时查看所有 HTTP 请求
- **工作流检查** - 一键检测流程配置问题
- **导入导出** - 工作流配置的导入导出功能

### 💾 数据管理
- **SQLite 存储** - 轻量级数据库，开箱即用
- **外部数据库** - 支持 MySQL/PostgreSQL 等多种数据库
- **存储管理** - 可视化管理存储文件

---

## 📦 安装

### 环境要求
- Python 3.10+
- pip

### 快速开始

```bash
# 克隆项目
git clone https://github.com/uuuftx/superweb.git
cd superweb

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m app.main
```

服务将在 http://localhost:8000 启动

访问管理界面: http://localhost:8000/ui/

---

## 🚀 使用指南

### 1. 创建工作流

1. 访问 http://localhost:8000/ui/workflows
2. 点击"新建工作流"按钮
3. 填写工作流名称和描述
4. 点击"创建工作流"

### 2. 编辑工作流

1. 在工作流列表中点击工作流名称
2. 进入代码编辑器
3. 点击"添加"按钮创建节点
4. 编写 Python 代码处理业务逻辑
5. 设置 `next_node` 指定下一个节点
6. 点击"保存"保存工作流

### 3. 调用工作流

```bash
# 通过统一的 API 接口调用
curl -X POST http://localhost:8000/workflow/api \
  -H "Content-Type: application/json" \
  -d '{"workflow_name": "你的工作流名称"}'
```

### 4. 节点代码示例

```python
# 节点 1: 开始节点
data = {
    "msg": "开始",
    "timestamp": datetime.now().isoformat()
}
next_node = 2  # 跳转到节点 2

# 节点 2: 处理数据
result = {
    "message": "工作流完成",
    "input": data,
    "processed": True
}
next_node = 0  # 0 表示结束
```

---

## 📁 项目结构

```
superweb/
├── app/
│   ├── api/              # API 路由
│   │   ├── workflows.py      # 工作流管理
│   │   ├── endpoints.py      # 端点管理
│   │   └── database_configs.py  # 数据库配置
│   ├── core/             # 核心功能
│   │   ├── config.py         # 配置管理
│   │   ├── database.py       # 数据库连接
│   │   └── request_logger.py # 请求日志
│   ├── engine/           # 工作流引擎
│   │   ├── loader.py         # 动态加载器
│   │   └── executor.py       # 执行器
│   ├── models/           # 数据模型
│   ├── services/         # 业务服务
│   ├── ui/               # 界面模板
│   └── utils/            # 工具函数
├── storage/              # 存储目录
├── tests/                # 测试文件
└── requirements.txt      # 依赖列表
```

---

## 🎯 功能演示

### 工作流列表
- 🔍 搜索和过滤工作流
- 📊 统计信息展示
- 📄 分页浏览
- ✅ 批量操作

### 代码编辑器
- 🎨 多主题支持（7种编辑器主题）
- 🔍 一键检查流程问题
- 📤 导出工作流配置
- 📋 查看执行日志

### 开发工具
- 🧪 API 测试器
- 📋 请求日志查看
- 📁 存储文件管理
- 📊 系统状态监控

---

## 🔌 API 端点

### 工作流管理
- `GET /api/admin/workflows` - 获取工作流列表
- `POST /api/admin/workflows` - 创建工作流
- `GET /api/admin/workflows/{id}` - 获取工作流详情
- `PATCH /api/admin/workflows/{id}` - 更新工作流
- `DELETE /api/admin/workflows/{id}` - 删除工作流
- `GET /api/admin/workflows/{id}/export` - 导出工作流
- `POST /api/admin/workflows/import` - 导入工作流

### 工作流执行
- `POST /workflow/api` - 统一的工作流调用接口

### 动态端点
- 动态生成的端点，基于数据库配置

---

## 🛠️ 开发

### 运行开发服务器

```bash
# 启动服务（自动重载）
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_workflows.py
```

### 代码规范

项目使用 Python 类型提示和异步编程模式：

```python
from typing import Optional
from fastapi import FastAPI

@app.get("/")
async def read_root():
    return {"message": "Hello World"}
```

---

## 📝 更新日志

### v1.0.0 (2026-02-09)
- ✨ 初始版本发布
- 🎨 可视化工作流编辑器
- 🔧 动态 API 端点支持
- 🛠️ 开发者工具面板
- 📊 分页、搜索、排序功能
- 🎨 多主题支持（深灰色/亮色）
- 🔍 工作流检查功能
- 📤 工作流导入导出

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📧 联系方式

- GitHub: [@uuuftx](https://github.com/uuuftx)
- Issues: [提交问题](https://github.com/uuuftx/superweb/issues)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！**

Made with ❤️ by [uuuftx](https://github.com/uuuftx)

</div>
