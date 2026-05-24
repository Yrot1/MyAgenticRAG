# AgenticRAG Vue FastAPI

## About

以**售后 / 客服知识库问答**为典型场景的智能 RAG 演示：前端使用 Vue 3 + Element Plus 构建深色科技风聊天界面，后端使用 FastAPI 提供认证、文档入库、向量检索、流式问答、Agentic RAG 和回答质量评估。项目集成 PostgreSQL、ChromaDB、可选 HyDE：用 LLM 生成假设文档片段作扩展查询，环境变量 USE_HYDE 控制开关。可选 **Redis**（Agent 会话共享与检索短期缓存）、LangChain、Embedding 模型、智谱 GLM / OpenAI-compatible API 与 RAGAS。仓库在 `backend/RAG/data` 附带 **星河科技 Nova 耳机 X1** 示例语料（用户手册、常见故障 FAQ、退换货政策、内部客服话术等），也可上传自有文档扩展为任意领域知识库，用于完整演示「文档入库 → 向量化检索 → 增强生成 → 质量评估」流程。

## 功能特性

- 文档入库：PDF / Word / 表格 / Markdown / TXT，解析切分后写入 Chroma；`backend/RAG/data` 提供上述售后演示 Markdown，可与自上传文档并存。
- RAG 问答：向量召回 + 上下文注入生成。
- 流式输出：SSE，前端边收边渲染。
- Agent 模式：任务规划、多轮检索、回答与自检，可展示思考过程与工具调用。
- Redis（可选）：配 `REDIS_URL` 后，Agent 服务端会话可多实例共享；普通 RAG 与 Agent 共用检索缓存（默认约 120s），减轻向量库与重排压力。不配则 Agent 会话仅存进程内、无检索缓存。
- 参考资料：回答可展开检索片段。
- 质量评估：RAGAS；Agent 内可选检索/答案评估。
- 用户与会话：注册登录、JWT；会话管理；消息与文件记录存 PostgreSQL。
- 部署：本地脚本、Docker / Compose、Nginx 示例。
- UI：Vue 3 + Element Plus 深色科技风。

## 项目结构

```text
RAG_vue_fastApi/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── RAG/
│   └── agent/
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 环境变量

先复制环境变量示例：

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

然后在 `.env` 中填写真实模型 Key：

```env
ZHIPUAI_API_KEY=your_zhipuai_api_key_here
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
CHAT_MODEL_NAME=glm-4.5-air
EMBEDDING_MODEL_NAME=embedding-2
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres
JWT_SECRET_KEY=replace_with_a_long_random_secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

**Redis（可选）**：在本机或服务器上启动 Redis 后，在 `.env` 中配置 `REDIS_URL`（示例见 `.env.example`）。常用变量：`REDIS_KEY_PREFIX`、`REDIS_CONVERSATION_TTL_SECONDS`（会话历史 TTL，默认 7 天）、`RETRIEVAL_CACHE_TTL_SECONDS`、`RETRIEVAL_CACHE_ENABLED`（有 `REDIS_URL` 时默认开启检索缓存）、`REDIS_MAX_CONNECTIONS`。当前 Compose 栈未内置 Redis 服务，生产或多副本部署时需自行接入实例。

`DATABASE_URL` 里的用户名、密码和数据库名需要与你本机 PostgreSQL 保持一致。后端启动时会自动创建项目需要的业务表。

前端默认通过 Vite 代理访问后端 `/api`。如果前后端分开部署，可以在 `frontend/.env` 中设置：

```env
VITE_API_BASE=http://127.0.0.1:8000
```

## 启动方法

### 一键开发启动（Windows）

```powershell
.\scripts\dev.ps1
```

这个脚本会分别打开后端和前端终端。首次运行前仍需安装依赖并配置 `.env`。

### 后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

后端默认运行在 `http://localhost:8000`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`。

也可以在项目根目录直接运行：

```bash
npm --prefix frontend run dev
```

## Docker Compose 部署（第五步）

在已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 的前提下：

1. 在项目根目录准备 `.env`（可从 `.env.example` 复制），填写 `ZHIPUAI_API_KEY`（或 `OPENAI_API_KEY`）、`JWT_SECRET_KEY` 等。`docker compose` 会读取该文件做变量替换并传入 `api` 容器；`DATABASE_URL` 由 compose 自动指向 `db` 服务，覆盖 `.env` 里本机数据库连接。
2. **前端在宿主机先构建**（`web` 镜像只含 Nginx + 静态文件，**不在容器内拉取 Node 镜像**，避免国内/IPv6 访问 `auth.docker.io` 失败）：`npm --prefix frontend ci && npm --prefix frontend run build`，或使用一键脚本 `.\scripts\docker-up.ps1`（含上述步骤与 `docker compose up --build -d`）。
3. 前端镜像把同一站点下的 `/api` 反向代理到后端；浏览器访问页面与接口同源，一般不触发 CORS 问题。
4. 持久化：`postgres_data` 存 Postgres 数据，`chroma_data` 存 Chroma 向量库挂载到容器内 `/workspace/backend/chroma_db`。数据库默认映射 **`${POSTGRES_PUBLISH_PORT:-5432}:5432`**，可用 DBeaver 等连接 **主机端口**、用户/库与 `POSTGRES_USER` / `POSTGRES_DB` 一致（与 compose 变量相同）；若本机已有 Postgres 占用 5432，在 `.env` 里把 `POSTGRES_PUBLISH_PORT` 改为例如 `5433`。

启动与停止：

```bash
npm --prefix frontend ci && npm --prefix frontend run build
docker compose up --build -d
docker compose logs -f api
docker compose down
```

Windows 一步启动（含前端构建）：

```powershell
.\scripts\docker-up.ps1
```

默认端口：**Web `http://localhost:8080`**，后端对外映射 **`http://localhost:8000`**（可在根目录 `.env` 中用 `FRONTEND_PUBLISH_PORT`、`BACKEND_PUBLISH_PORT` 调整）。

若在远程主机或 HTTPS 域名上部署，请将 `DOCKER_CORS_ORIGINS` 设为前端实际 Origin（或通过反代让所有请求同源，仅保留 Nginx→后端的链路）。

镜像构建会忽略 `frontend/node_modules` 与向量库等大目录（见 `.dockerignore`）；**`frontend/dist` 会打入 `web` 镜像**，故构建前须完成 `npm run build`。

构建 **api** 时若在 `apt-get` 中出现 **502 Bad Gateway**（源自 `deb.debian.org` CDN），可先**直接重试** `docker compose build api`。若经常出现，可在根目录 `.env` 设置 `DEBIAN_REPO_MIRROR=http://mirrors.aliyun.com`（或清华等可用的 Debian HTTP 镜像主机前缀）后再构建。

## 常用命令

```powershell
# 一键开发启动
.\scripts\dev.ps1

# 本地检查：Python 语法 + 前端构建
.\scripts\check.ps1

# Docker Compose（先构建 frontend/dist，或由 docker-up.ps1 代劳）
npm --prefix frontend run build
docker compose up --build -d

# 宿主机构建前端 + 启动 Compose（一条龙）
.\scripts\docker-up.ps1

# 前端开发
npm --prefix frontend run dev

# 前端构建
npm --prefix frontend run build

# 后端启动
python backend/main.py
```

## 运行检查

后端启动后访问：

```text
http://127.0.0.1:8000/api/health
```

正常会返回服务状态、模型名、Embedding 模型名、CORS 配置，以及 `api_key_configured` 是否为 `true`。如果它是 `false`，说明 `.env` 没有正确配置模型 Key。若配置了 Redis，还会返回 `redis_configured`、`redis_ping_ok`、`redis_retrieval_cache_enabled`，便于确认连接与检索缓存开关。

## API 接口

- `POST /api/auth/register`：注册用户并返回登录 token
- `POST /api/auth/login`：登录并返回登录 token
- `GET /api/auth/me`：获取当前登录用户
- `GET /api/conversations`：获取当前用户的会话列表
- `POST /api/conversations`：创建当前用户的会话
- `POST /api/chat`：发送聊天消息，支持流式返回
- `POST /api/upload`：上传文件到知识库
- `GET /api/files`：查看已入库文件
- `POST /api/evaluate`：评估回答质量
- `GET /api/health`：健康检查（含 Redis 连接与检索缓存开关字段，未配置 Redis 时相应字段为 false 或 null）

## Git 提交注意

不要提交以下内容：

- `.env`、真实 API Key 或任何密钥
- `frontend/node_modules/`
- `frontend/dist/`
- `backend/chroma_db/`
- 上传文件、向量库、缓存、日志文件

这些内容已写入 `.gitignore`。上传 GitHub 前建议再检查一次是否存在真实密钥。

## 技术栈

- 前端：Vue 3、Vite、Element Plus、Axios。
- 后端：FastAPI、Uvicorn、Pydantic、python-dotenv。
- 数据：PostgreSQL、SQLAlchemy、psycopg；ChromaDB、langchain-chroma（向量库目录 `backend/chroma_db`）。
- 缓存（可选）：Redis、redis-py。
- RAG / LLM：LangChain 全家桶、OpenAI 兼容 Embeddings 与 Chat（智谱 GLM / zhipuai、`langchain-openai`）。
- Agent：规划 / 检索 / 回答 / 评估流水线；SSE 流式。
- 评估：RAGAS、datasets。
- 认证：JWT、bcrypt。
- 部署：Docker、Compose、Nginx。
