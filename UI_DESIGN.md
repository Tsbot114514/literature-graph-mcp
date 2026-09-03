# 可视化交互界面（UI）设计文档

> 目标读者：协作者（supxc）与作者（Tsbot114514）。本阶段只做**只读查看**，编辑功能后续阶段再加。

## 1. 目标

给 literature-graph-mcp 增加一个**浏览器可视化交互界面**，让"人"（而非 AI 助手）能够：

- 可视化查看知识图谱（节点 + 关系）
- 搜索节点 / 论文
- 查看节点详情和一跳邻域

第一阶段只读，不写任何数据；编辑、删除/合并放到后续阶段。

## 2. 现状与约束

现有架构（分层清晰，是加界面的基础）：

```
AI 助手 ──stdio(MCP)──▶ server.py ──▶ repository.py ──▶ Neo4j
```

- `server.py`：MCP 工具定义（stdio 接口，只服务 AI，没有给人用的界面）
- `repository.py`：所有 Neo4j 读写逻辑集中在 `LiteratureGraphRepository`
- `DESIGN.md`：规则中枢（身份去重、note 格式、权限边界）

关键约束：

- MCP 本身不提供人机界面，UI 是**新增的独立入口**
- 删除 / 合并需"用户显式授权"，第一版不暴露（本 UI 未来可能成为授权的天然场景，但要先和作者对齐）
- 环境变量由 `install.ps1` 写入：`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`、`LITERATURE_LIBRARY_PATH`

## 3. 核心原则

1. **复用 repository 层**：UI 通过 `LiteratureGraphRepository` 访问 Neo4j，绝不写裸 Cypher，避免与 `DESIGN.md` 规则冲突
2. **不破坏 MCP**：UI 是加法，不动 `server.py` 的 stdio 行为
3. **只做加法**：阶段 1 只读，不引入任何写操作
4. **分层清晰**：浏览器 → HTTP API（FastAPI）→ `repository.py` → Neo4j

## 4. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端 | FastAPI + uvicorn | 与现有项目同为 Python；代码量小 |
| 前端 | Cytoscape.js（CDN）+ 单个 index.html | 专为交互式节点-边图设计；无需前端框架 |
| 图数据 | 复用 `LiteratureGraphRepository` | 保证规则一致 |

## 5. 架构

```
浏览器 (index.html + Cytoscape.js)
   │  HTTP JSON
   ▼
FastAPI 应用（新增模块，如 src/literature_graph_mcp/ui/）
   │  复用
   ▼
LiteratureGraphRepository (repository.py)
   │  bolt
   ▼
Neo4j
```

## 6. 启动方式

新增 CLI 子命令（或 `--ui` 参数），读取已设置的环境变量：

```powershell
uv run literature-graph-mcp ui --port 8000
```

启动流程与 `server.py:main()` 类似：

1. `resolve_library_root(args.library)` 绑定文献库
2. 用 `NEO4J_URI/USER/PASSWORD` 构建 `LiteratureGraphRepository`
3. `repository.verify()` + `repository.ensure_schema()`
4. 启动 FastAPI/uvicorn，监听 `localhost:8000`

## 7. API 设计（阶段 1，全部只读）

| 方法 | 路径 | 说明 | 复用的 repository 方法 |
|---|---|---|---|
| GET | `/` | 返回 index.html | — |
| GET | `/api/search?q=&limit=` | 搜索节点/论文 | `search_nodes` / `search_papers` |
| GET | `/api/node/{id}` | 节点详情（属性+note+chunk） | `get_node` |
| GET | `/api/node/{id}/neighborhood` | 一跳邻域（图渲染用） | `get_neighborhood` |
| GET | `/api/papers` | 论文列表 | `list_papers` |
| GET | `/api/path?source=&target=` | 两点路径（可选） | `find_path` |

## 8. 前端交互（阶段 1）

- 顶部搜索框 + 结果列表（点击结果加载对应节点）
- 以选中节点为中心渲染邻域图（节点按类型着色：Paper/Author/Topic/…）
- 关系按类型显示标签（CITES/SUPPORTS/QUALIFIES/…）
- 点击节点弹出详情面板（属性、note、chunk）

## 9. 分阶段计划

- **阶段 1（当前）**：只读查看器（搜索 + 图渲染 + 详情）
- **阶段 2**：编辑（新建/修改节点与关系，包装现有 `upsert_*` 方法）
- **阶段 3**：删除 / 合并（需与作者对齐授权交互，呼应 `DESIGN.md` 第 12/13 节）
- **阶段 4**：测试 + 文档（给 UI API 层加测试，更新 README）

## 10. 待与作者对齐的问题

1. UI 代码目录结构（新目录 `src/literature_graph_mcp/ui/`？）
2. 依赖：`fastapi`、`uvicorn` 是否加入 `pyproject.toml`（当前只有 `mcp` + `neo4j`）
3. 是否需鉴权（本地 localhost 单用户？）
4. 编辑功能的权限边界（UI 允许哪些写操作）
5. 命令入口命名（`ui` 子命令 vs `--ui` 参数）
