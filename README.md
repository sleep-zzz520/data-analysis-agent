# 🚀 智能数据分析 Agent

面向企业 MySQL 多库 + 上传文件的数据分析对话助手。用自然语言提问，Agent 自动查库、算数、出图。

## ✨ 功能特性

- **自然语言 → SQL**:Agent 自动完成库/表感知、SQL 生成与执行、报错自修正(最多 3 次重试),全程只读(SELECT)。
- **上传文件真实分析**:上传 CSV/Excel 后,Agent 用 `query_file`(duckdb SQL)真实读取文件数据,不再靠预览猜测;支持分组统计、多图表可视化。
- **多图表输出**:一轮对话可同时生成多张 ECharts 交互图 + matplotlib 静态图(此前只保留最后一张的问题已修复)。
- **流式输出**:SSE 流式逐字返回,可实时看到回复生成过程。
- **Markdown 渲染**:AI 回复以规范排版显示(标题/列表/代码块/表格),原始 `# * -` 符号不裸露。
- **配置中心**:
  - LLM 配置:支持 OpenAI / Anthropic / 通义千问 三家,选提供商自动填充接口地址,API Key 加密存储,保存后自动测试连接。
  - 数据库配置:MySQL 连接参数加密保存。
- **会话管理**:历史会话列表、加载、删除、**内联重命名**。
- **用户账号与数据隔离**:开放注册/登录(JWT 认证),每个用户的会话与上传文件互相隔离;LLM/DB 配置全局共享(管理员配置一次即可)。
- **UI**:白黑主题、通栏布局(会话栏贴左、对话区贴右)。

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Axios + ECharts + marked/DOMPurify |
| 后端 | Python 3.9 + FastAPI + LangChain / LangGraph + SQLAlchemy + Pandas + duckdb |
| 存储 | SQLite(会话/上传元信息)、JSON 加密文件(LLM/DB 配置)、文件系统(上传文件本体) |

## 📁 目录结构

```
DataAnalysis_Agent/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口、CORS、路由挂载
│   │   ├── api/
│   │   │   ├── chat_api.py    # 对话(含 SSE 流式)、上传、会话管理
│   │   │   └── config_api.py  # LLM / 数据库配置与测试连接
│   │   ├── agent/
│   │   │   ├── graph.py       # LangGraph Agent 图
│   │   │   ├── prompts.py     # System Prompt(工作流/可视化/回复格式约束)
│   │   │   └── state.py
│   │   ├── tools/
│   │   │   ├── agent_tools.py # list_schemas / get_schema / query_mysql / make_chart
│   │   │   ├── chart_tool.py  # generate_chart / auto_analyze_and_visualize(8 种图表)
│   │   │   └── file_tool.py   # list_files / query_file(duckdb) / file_stats
│   │   ├── core/factories.py  # 按提供商构建 LLM、构建数据库引擎
│   │   ├── meta/              # 配置加密存储(store / crypto)
│   │   ├── memory/            # 内存会话存储(LRU)
│   │   ├── persistence/       # SQLite 会话/上传持久化
│   │   ├── errors/            # 错误分类
│   │   └── db/schema.py       # 多库表结构读取
│   ├── data/                  # 运行时数据(见下)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/             # ChatView(对话) / ConfigView(配置中心)
│   │   ├── components/        # ChartView / DataTable / MarkdownContent / 表单等
│   │   ├── api/               # 接口封装(含 SSE 流式)
│   │   ├── stores/            # Pinia
│   │   └── router/
│   └── package.json
└── README.md
```

### backend/data/ 说明

| 文件 | 用途 |
|---|---|
| `chat_history.db` | SQLite:会话、消息、上传元信息 |
| `uploads/` | 上传文件本体(服务重启不丢) |
| `llm_configs.json` / `db_configs.json` | 配置(Key 加密) |
| `.master_key` | 加密密钥文件 |

## 🐳 Docker 部署

```bash
# 构建并启动（前端 http://localhost:8080，后端 http://localhost:8000）
docker compose up -d --build
# 查看日志
docker compose logs -f
# 停止
docker compose down
```

- 后端镜像：`python:3.9-slim`，非 root 运行，内置中文字体，`backend/data/` 以卷挂载持久化。
- 前端镜像：多阶段构建（node 构建 → nginx 托管），nginx 代理 `/api` 到后端并关闭缓冲以支持 SSE 流式输出，内置 Vue Router history 路由 fallback。
- 首次启动后在「配置中心」填写 LLM/DB 配置即可使用。

## 🚀 快速开始

> **Clone 后注意**:`backend/data/`(运行时数据)不会随仓库分发——首次启动会自动创建 `data/` 目录,LLM/DB 配置请在页面「配置中心」里填写(密钥加密保存),无需任何环境变量。

### 1. 后端(端口 8000)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # 首次
pip install -r requirements.txt                     # 首次
python app/main.py
```

启动后自检会打印已注册路由;若缺少依赖(如 matplotlib/duckdb/langchain-anthropic),按 `requirements.txt` 补齐。

### 2. 前端(端口 5173)

```bash
cd frontend
npm install      # 首次
npm run dev
```

访问 http://localhost:5173 ,`/api` 已代理到后端 8000。

### 3. 首次使用

1. 打开「配置中心」,新增 **LLM 配置**(选提供商→自动填接口地址→填 API Key→模型名→保存并测试)。
2. 新增**数据库配置**(MySQL 主机/端口/账号,建议用只读账号)。
3. 回到「分析对话」,提问或上传 CSV/Excel 分析。

## 🧪 自动化测试

```bash
# 后端 pytest（核心逻辑单测 + 认证接口集成，132 例）
cd backend
pip install -r requirements-dev.txt   # 首次
python -m pytest tests/

# 前端 vitest（拦截器 / SSE 解析 / 组件 / 路由守卫 / store，26 例）
cd frontend
npm install          # 首次
npm test
```

> 测试全程隔离：后端把 SQLite / 配置 JSON / JWT 密钥重定向到临时目录，不触碰真实 `backend/data/`；前端在 happy-dom 环境运行，不启动后端。CI（GitHub Actions）已包含两端测试步骤。

## 💬 使用示例

- 数据库分析:`上个月各状态的订单数?` → Agent 查库返回表格 + 洞察
- 上传文件:`上传成绩单.csv`,`各科平均分并画柱状图` → Agent 真实统计文件数据并出图
- 一轮多图:可要求同时生成柱状图与饼图,前端全部展示

## 🛠 Agent 工具一览

| 工具 | 作用 |
|---|---|
| `list_schemas` / `get_schema` | 多库发现、表结构读取 |
| `query_mysql` | 只读 SQL 查询(自动 LIMIT 500) |
| `make_chart` | 基础 ECharts 图(bar/line/pie) |
| `generate_chart` | 高级图表(8 种:bar/line/pie/scatter/histogram/boxplot/area/heatmap) |
| `auto_analyze_and_visualize` | 自动选型 + 统计摘要 |
| `list_files` / `query_file` / `file_stats` | 上传文件结构、SQL 查询(duckdb)、统计摘要 |

## ⚠️ 注意事项

- **LLM 密钥**:需有效 API Key(免费额度耗尽会返回 403),在「配置中心」填写,加密保存在 `backend/data/` 中。
- **数据库安全**:系统强制只读 SELECT,但请仍使用**只读账号**连接,避免权限过大。
- **数据路径**:所有运行时数据固定在 `backend/data/`(绝对路径),从任意目录启动后端都不会分裂数据。
- **图表中文**:后端使用 matplotlib `Agg` 无界面后端,避免 macOS 下后台线程崩溃;首次启动会构建字体缓存。
- **会话上限**:内存会话默认最多 200 个、单会话 50 轮,超出自动淘汰/截断(历史仍保留在 SQLite)。

## 📄 License

内部项目,无开源许可。
