# SuperWeb

> 可视化API开发框架 - 通过网页界面配置来开发API接口

## 特性

- **网页界面配置**：无需编写代码，通过可视化界面配置API端点
- **自动CRUD**：定义数据模型后自动生成增删改查接口
- **逻辑编排**：可视化编排业务逻辑（开发中）
- **动态路由**：配置实时生效，支持热重载
- **API文档**：基于FastAPI自动生成OpenAPI文档
- **轻量部署**：基于SQLite，无需额外数据库

## 快速开始

### 安装

```bash
# 克隆项目
cd superweb

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
# 启动服务
python -m app.main
```

访问：
- 管理界面：http://localhost:8000/ui/
- API文档：http://localhost:8000/docs

## 使用指南

### 1. 创建数据模型

在"数据模型"页面创建模型和字段：
- 模型名称：User
- 数据表名：users
- 字段：name (string), email (string), age (integer)

### 2. 创建API端点

在"API端点"页面创建接口：
- 路径：/api/users
- 方法：GET/POST/PUT/DELETE
- 逻辑类型：数据库CRUD
- 关联模型：User

### 3. 测试API

访问 /docs 测试自动生成的API接口

## 项目结构

```
superweb/
├── app/
│   ├── core/           # 核心配置、数据库
│   ├── models/         # 配置数据模型
│   ├── engine/         # 动态路由引擎
│   ├── api/            # 管理API
│   ├── ui/             # 网页界面
│   └── main.py         # 应用入口
├── storage/            # SQLite数据库
└── requirements.txt
```

## 逻辑类型说明

### Simple（简单响应）
- 自定义代码执行
- 固定响应模板
- 支持变量替换：`{{context.query.name}}`

### CRUD（数据库操作）
- GET /api/users - 列表（支持分页）
- GET /api/users/1 - 详情
- POST /api/users - 创建
- PUT /api/users/1 - 更新
- DELETE /api/users/1 - 删除

### Workflow（工作流）
- 可视化逻辑编排（开发中）
- 支持条件判断、数据处理、API调用等

## 开发路线

- [ ] 完善工作流编辑器
- [ ] 支持更多数据库（PostgreSQL、MySQL）
- [ ] API参数配置界面
- [ ] 响应模板编辑器
- [ ] 权限管理
- [ ] API版本控制
- [ ] 导入/导出配置

## 许可证

MIT License
