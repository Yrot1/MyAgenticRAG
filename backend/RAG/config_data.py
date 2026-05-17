import os

# 获取 RAG 目录（当前文件所在目录）
RAG_DIR = os.path.dirname(os.path.abspath(__file__))

# 获取 backend 目录（RAG 的父目录）
BACKEND_DIR = os.path.dirname(RAG_DIR)

# 获取项目根目录
PROJECT_DIR = os.path.dirname(BACKEND_DIR)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_DIR, ".env"))
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except ImportError:
    pass

# MD5 文件路径（存放在 RAG 目录）
md5_path = os.path.join(RAG_DIR, "md5.text")

# Chroma 数据库路径（存放在 backend 目录）
collection_name = "rag"
persist_directory = os.path.join(BACKEND_DIR, "chroma_db")

# spliter
chunk_size = 1000
chunk_overlap = 100
separators=["\n\n","\n",".","!","?","。","！","？"," ",""]
max_split_char_number = 1000  # 文本分割的阈值

# 向量检索：LangChain as_retriever 的 search_kwargs["k"]（命名历史原因沿用 similarity_threshold）
similarity_threshold = 5
# 与普通 RAG / Agent 共用（优先使用 retrieval_k）
retrieval_k = 5
# MMR：先从向量库取 fetch_k 条再压缩为 k 条，减轻相邻切片冗余
retrieval_fetch_k = 24
use_mmr_retriever = True

# 高级检索（Agent / 统一检索服务）
agent_max_subtasks = int(os.getenv("AGENT_MAX_SUBTASKS", "4"))
use_hyde = os.getenv("USE_HYDE", "true").lower() in ("1", "true", "yes")
use_rerank = os.getenv("USE_RERANK", "true").lower() in ("1", "true", "yes")
rerank_candidate_k = int(os.getenv("RERANK_CANDIDATE_K", "16"))
use_ragas_in_agent = os.getenv("USE_RAGAS_IN_AGENT", "true").lower() in ("1", "true", "yes")
ragas_faithfulness_threshold = float(os.getenv("RAGAS_FAITHFULNESS_THRESHOLD", "0.55"))
ragas_answer_relevancy_threshold = float(os.getenv("RAGAS_ANSWER_THRESHOLD", "0.5"))
agent_max_retrieval_attempts = int(os.getenv("AGENT_MAX_RETRIEVAL_ATTEMPTS", "2"))
agent_retrieval_threshold = float(os.getenv("AGENT_RETRIEVAL_THRESHOLD", "0.6"))
agent_answer_threshold = float(os.getenv("AGENT_ANSWER_THRESHOLD", "0.65"))
# 并行：多路向量检索、HyDE/子任务 query 构建（ThreadPool）
use_parallel_retrieval = os.getenv("USE_PARALLEL_RETRIEVAL", "true").lower() in ("1", "true", "yes")
# 子任务是否再调 LLM 转写 query；false 时直接用子任务原文检索（更快）
use_llm_subtask_query = os.getenv("USE_LLM_SUBTASK_QUERY", "false").lower() in ("1", "true", "yes")
# Agent 内 LLM 检索/答案评估（默认关，避免 FAQ 类问题多 2 次 LLM）
use_agent_retrieval_eval = os.getenv("USE_AGENT_RETRIEVAL_EVAL", "false").lower() in ("1", "true", "yes")
use_agent_answer_eval = os.getenv("USE_AGENT_ANSWER_EVAL", "false").lower() in ("1", "true", "yes")

# 星河科技演示语料目录
sample_data_dir = os.path.join(RAG_DIR, "data")

llm_api_key = os.getenv("ZHIPUAI_API_KEY") or os.getenv("OPENAI_API_KEY")
openai_api_base = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "embedding-2")
chat_model_name = os.getenv("CHAT_MODEL_NAME", "glm-4.5-air")

# FastAPI runtime
backend_host = os.getenv("BACKEND_HOST", "0.0.0.0")
backend_port = int(os.getenv("BACKEND_PORT", "8000"))
cors_allow_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

# PostgreSQL and auth
database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Redis（可选）：多实例共享 Agent 会话历史 + 检索片段短期缓存
redis_url = os.getenv("REDIS_URL", "").strip()
redis_key_prefix = (os.getenv("REDIS_KEY_PREFIX", "rag") or "rag").strip()
redis_conversation_ttl_seconds = int(
    os.getenv("REDIS_CONVERSATION_TTL_SECONDS", str(7 * 24 * 3600))
)
redis_retrieval_cache_ttl_seconds = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "120"))
redis_max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
redis_retrieval_cache_enabled = bool(redis_url) and os.getenv(
    "RETRIEVAL_CACHE_ENABLED", "true"
).lower() in ("1", "true", "yes")

session_config = {
    "configurable": {
        "session_id": "user_001"
    }
}
















