# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start the development server
python -m app.main
```

The server starts on http://localhost:8000 by default. Access points:
- UI: http://localhost:8000/ui/
- API Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Configuration

Configuration is managed in `app/core/config.py` using `pydantic-settings`. Settings can be overridden via environment variables or a `.env` file:

- `DATABASE_URL`: SQLite database path (default: `sqlite+aiosqlite:///./storage/superweb.db`)
- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)
- `DEBUG`: Enable debug mode (default: `True`)
- `UI_ENABLED`: Enable web UI (default: `True`)

## Architecture Overview

SuperWeb is a visual API development framework where users can configure API endpoints through a web interface without writing code.

### Core Components

1. **Dynamic Router Loader** (`app/engine/router_loader.py`)
   - Loads API endpoint configurations from the database at startup
   - Dynamically registers routes with FastAPI
   - Each endpoint's logic is executed through `execute_endpoint()`

2. **Executor Engine** (`app/engine/executor.py`)
   - Executes different endpoint logic types:
     - `simple`: Custom Python code or fixed response templates
     - `workflow`: Visual workflow orchestration (Python script nodes)
     - `crud`: Auto-generated database CRUD operations
     - `custom`: Custom Python code execution
   - Workflow execution follows a sequential node-based model where nodes are numbered by `position_x / 200`
   - Python nodes execute with a controlled global environment (see `execute_python_node()`)

3. **Data Models** (`app/models/`)
   - `Endpoint`: API endpoint configuration with path, method, logic_type
   - `DataModel`: User-defined data models with fields
   - `Workflow`: Visual workflow definitions with nodes and connections
   - `WorkflowNode`: Individual workflow nodes with config stored as JSON
   - `WorkflowExecutionLog`: Execution logging (stored as files in `storage/workflow_logs/`)

4. **Database** (`app/core/database.py`)
   - Uses SQLAlchemy 2.0 with async support
   - SQLite with aiosqlite for lightweight deployment
   - Session factory: `async_session_maker`
   - All models inherit from `Base` in `app.core.database`

### Request Flow

1. Application startup (`app/main.py`):
   - `lifespan()` initializes database tables
   - `loader.load_all_endpoints()` loads enabled endpoints from DB
   - Dynamic routes are registered with FastAPI

2. Incoming request:
   - FastAPI routes to dynamically registered endpoint handler
   - `execute_endpoint()` builds context (path, query, body, headers)
   - Based on `endpoint.logic_type`, dispatches to appropriate executor
   - Returns result as JSON response

3. Workflow execution (for `logic_type="workflow"`):
   - Nodes are ordered by `position_x` (node number = position_x / 200)
   - Execution starts at node 1, proceeds via `next_node` variable
   - Each Python node can set `next_node`, `response`, `result`, or `data` variables
   - Execution logs saved to `storage/workflow_logs/` when enabled

### Endpoint Logic Types

**Simple (`logic_type="simple"`)**
- Executes `custom_code` if provided
- Otherwise renders `response_template` with variable substitution (e.g., `{{context.query.name}}`)

**Workflow (`logic_type="workflow"`)**
- Executes sequential Python script nodes
- Each node's code stored in `node.config['code']`
- Node transitions controlled by `next_node` variable (0 or negative to end)
- Access to context: `context.path`, `context.query`, `context.body`, `context.headers`

**CRUD (`logic_type="crud"`)**
- Auto-generates database operations for a DataModel
- GET with `id` path param: single record
- GET without `id`: paginated list (page, page_size query params)
- POST: create record
- PUT with `id`: update record
- DELETE with `id`: delete record

**Custom (`logic_type="custom"`)**
- Executes `endpoint.custom_code` with controlled globals
- Return value via `result` variable

### Workflow Node Execution

Python nodes have access to a controlled global environment including:
- Standard library modules: `json`, `datetime`, `time`, `uuid`, `random`, `re`, `hashlib`, `base64`, `math`, `collections`, `itertools`, `functools`, `typing`, `os`, `sys`, `pathlib`, `string`, `copy`, `decimal`, `statistics`, `pickle`, `urllib`, `html`, `xml`, `sqlite3`, `logging`, `dataclasses`, `enum`, `numbers`, `ipaddress`
- Optional modules: `dateutil`, `httpx`
- Context variables: `data` (current workflow data), `context` (request context), `request`, `node` (node number), `node_name`

Node return variables:
- `next_node`: Next node number to execute (0 or negative to end)
- `response` / `result` / `data`: Output data passed to next node

### UI Templates

Located in `app/ui/templates/` using Jinja2:
- `index.html`: Main dashboard
- `workflows.html`: Workflow list and management
- `workflow_code_editor.html`: Visual workflow editor with code editor
- `workflow_logs.html`: Execution log viewer

### Management API

Admin API endpoints under `/api/admin/`:
- `/endpoints`: CRUD for endpoint configurations
- `/models`: CRUD for data models and fields
- `/workflows`: CRUD for workflow definitions
- `/workflows/{id}/nodes`: Save workflow nodes and connections
- `/workflows/{id}/detail`: Get workflow with nodes and connections
- `/workflows/{id}/logs`: Get execution logs for a workflow
- `/workflows/{id}/logs/{filename}`: Get specific log file content

## Storage

- SQLite database: `storage/superweb.db`
- Workflow execution logs: `storage/workflow_logs/*.log`
- Static files: `app/ui/static/`

## Important Notes

- Workflow node numbering is calculated as `int(position_x / 200)` - nodes must be positioned at multiples of 200
- The unified workflow API endpoint is `/workflow/api` - POST with `{"workflow_name": "..."}`
- Hot reload of endpoints is planned but not fully implemented (see `/api/admin/endpoints/reload`)
- Custom code execution uses a restricted `__builtins__` for security
- Workflow execution has a 1000 iteration limit to prevent infinite loops
- Database tables for DataModels are created/updated when models or fields are saved via admin API
