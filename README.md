# RAG Vue FastAPI

一个面向个人知识库场景的 RAG 问答系统，前端使用 Vue 3 + Element Plus 构建深色科技风聊天界面，后端使用 FastAPI 提供认证、文档入库、向量检索、流式问答、Agentic RAG 和回答质量评估能力。项目集成 PostgreSQL、ChromaDB、LangChain、Embedding 模型、智谱 GLM / OpenAI-compatible API 与 RAGAS，可用于演示完整的“文档上传 -> 向量化入库 -> 检索增强生成 -> 质量评估”流程。

## 功能特性

- 多格式文档入库：支持 PDF、Word、CSV、Excel、Markdown、TXT 等文件上传，自动完成文本解析、切分、Embedding 生成和 ChromaDB 向量索引写入。
- 检索增强问答：基于 LangChain + ChromaDB 从个人知识库中召回相关片段，并将上下文注入大模型生成回答，降低纯模型幻觉。
- 流式聊天体验：普通 RAG 问答路径使用 SSE `text/event-stream` 返回模型增量内容，前端通过 `ReadableStream` 边接收边渲染。
- Agentic RAG 模式：支持任务规划、多轮检索、回答生成、质量自检和工具调用记录展示，用于观察一次复杂问答的执行过程。
- 参考资料追溯：每次回答可展开查看检索到的上下文片段，方便判断答案是否来自知识库内容。
- 回答质量评估：集成 RAGAS，对回答的忠实度、相关性和综合质量进行评分，也包含 Agent 内部的检索质量与答案质量评估。
- 用户与会话管理：支持注册登录、JWT 鉴权、会话新建/切换/重命名/删除，历史消息和文件记录持久化到 PostgreSQL。
- 工程化部署：提供本地开发脚本、Dockerfile、Docker Compose 和 Nginx 反向代理配置，可一键启动前端、后端、PostgreSQL 与向量库持久化环境。
- 深色科技风 UI：基于 Vue 3、Element Plus、Vite 和 Axios 实现聊天、上传、评估面板、思考过程面板与响应式交互。


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

正常会返回服务状态、模型名、Embedding 模型名、CORS 配置，以及 `api_key_configured` 是否为 `true`。如果它是 `false`，说明 `.env` 没有正确配置模型 Key。

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
- `GET /api/health`：健康检查


## 技术栈

- 前端工程：Vue 3、Vite 5、Element Plus、Axios，用于构建知识库聊天界面、会话管理、文件上传、参考资料展示和回答评估面板。
- 后端服务：FastAPI、Uvicorn、Pydantic / Pydantic Settings、python-dotenv，提供认证、会话、聊天、上传、检索、评估和健康检查等 REST API。
- 数据库与持久化：PostgreSQL 16、SQLAlchemy 2、psycopg 3，保存用户、会话、消息、文件入库记录等业务数据；Docker Compose 中通过 `postgres_data` 持久化。
- 向量数据库：ChromaDB、langchain-chroma，用于存储文档切分后的向量索引；本地路径为 `backend/chroma_db`，Docker Compose 中通过 `chroma_data` 持久化。
- RAG 编排：LangChain、langchain-core、langchain-community、langchain-text-splitters，负责文档加载、文本切分、向量检索、上下文拼接和检索增强问答。
- Embedding：OpenAI-compatible Embeddings / 智谱 `embedding-2`，通过 `EMBEDDING_MODEL_NAME` 配置，和 ChromaDB 配合完成语义检索。
- 大模型接入：智谱 GLM / OpenAI-compatible API、langchain-openai、zhipuai，默认使用 `glm-4.5-air`，也可以通过 `OPENAI_API_BASE`、`CHAT_MODEL_NAME` 切换兼容接口和模型。
- Agentic RAG：规划 Agent、检索 Agent、回答 Agent、评估 Agent，支持任务拆解、多轮检索、工具调用记录、思考过程展示和答案质量自检。
- 回答质量评估：RAGAS、datasets，基于 `faithfulness`、`answer_relevancy` 和综合评分评估回答是否忠实于检索上下文、是否切题。
- 流式交互：FastAPI `StreamingResponse`、SSE `text/event-stream`、前端 Fetch `ReadableStream`，普通 RAG 路径支持模型增量输出；Agent 路径返回答案分块、思考过程、工具调用和评估元数据。
- 认证与安全：JWT、PyJWT、bcrypt，支持用户注册登录、Token 鉴权和密码哈希存储。
- 部署与反向代理：Docker Compose、Nginx、Dockerfile，组合前端静态站点、后端 API、PostgreSQL 和 Chroma 持久化存储。
