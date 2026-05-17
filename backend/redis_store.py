"""
Redis：仅用于 (1) 多实例共享会话历史 (2) 检索结果短期缓存。
未配置 REDIS_URL 时会话回退进程内字典，检索不做缓存。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from RAG import config_data as config

try:
    import redis
except ImportError:
    redis = None  # type: ignore

_pool: Optional["redis.ConnectionPool"] = None
_local_sessions: Dict[str, List[Dict[str, Any]]] = {}


def _redis_url() -> str:
    return (getattr(config, "redis_url", None) or "").strip()


def _client():
    global _pool
    url = _redis_url()
    if not url or redis is None:
        return None
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=int(getattr(config, "redis_max_connections", 20)),
        )
    return redis.Redis(connection_pool=_pool)


def redis_ping() -> bool:
    r = _client()
    if not r:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False


def normalize_query(q: str) -> str:
    q = (q or "").strip().lower()
    return re.sub(r"\s+", " ", q)


def _session_key(session_id: str) -> str:
    prefix = getattr(config, "redis_key_prefix", "rag")
    return f"{prefix}:sess:{session_id}:history"


def _retrieval_key_parts(
    metadata_filter: Optional[dict],
    question: str,
    subtasks: Optional[List[str]],
    use_hyde: Optional[bool],
    extra_queries: Optional[List[str]],
) -> str:
    uid = str((metadata_filter or {}).get("user_id", ""))
    hyde_val = use_hyde
    if hyde_val is None:
        hyde_val = getattr(config, "use_hyde", True)
    parts = (
        uid,
        normalize_query(question),
        json.dumps(list(subtasks or []), sort_keys=True, ensure_ascii=False),
        json.dumps(bool(hyde_val), sort_keys=True),
        json.dumps(list(extra_queries or []), sort_keys=True, ensure_ascii=False),
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    prefix = getattr(config, "redis_key_prefix", "rag")
    return f"{prefix}:retr:{digest}"


def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    r = _client()
    if r:
        try:
            raw = r.get(_session_key(session_id))
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return []
            return []
        except Exception as e:
            print(f"[redis_store] get_session_history failed: {e}")
            return []
    return [dict(x) for x in _local_sessions.get(session_id, [])]


def set_session_history(session_id: str, messages: List[Dict[str, Any]]) -> None:
    ttl = int(getattr(config, "redis_conversation_ttl_seconds", 604800))
    r = _client()
    key = _session_key(session_id)
    if r:
        try:
            if messages:
                r.set(key, json.dumps(messages, ensure_ascii=False))
                r.expire(key, ttl)
            else:
                r.delete(key)
        except Exception as e:
            print(f"[redis_store] set_session_history failed: {e}")
        return
    if messages:
        _local_sessions[session_id] = [dict(x) for x in messages]
    elif session_id in _local_sessions:
        del _local_sessions[session_id]


def append_session_turn(
    session_id: str,
    user_entry: Dict[str, Any],
    assistant_entry: Dict[str, Any],
) -> None:
    hist = get_session_history(session_id)
    hist.append(dict(user_entry))
    hist.append(dict(assistant_entry))
    set_session_history(session_id, hist)


def clear_session_history(session_id: str) -> None:
    set_session_history(session_id, [])


def get_retrieval_cached(
    metadata_filter: Optional[dict],
    question: str,
    *,
    subtasks: Optional[List[str]] = None,
    use_hyde: Optional[bool] = None,
    extra_queries: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not getattr(config, "redis_retrieval_cache_enabled", False):
        return None
    r = _client()
    if not r:
        return None
    key = _retrieval_key_parts(metadata_filter, question, subtasks, use_hyde, extra_queries)
    try:
        raw = r.get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_retrieval_cached(
    metadata_filter: Optional[dict],
    question: str,
    payload: Dict[str, Any],
    *,
    subtasks: Optional[List[str]] = None,
    use_hyde: Optional[bool] = None,
    extra_queries: Optional[List[str]] = None,
) -> None:
    if not getattr(config, "redis_retrieval_cache_enabled", False):
        return
    r = _client()
    if not r:
        return
    ttl = int(getattr(config, "redis_retrieval_cache_ttl_seconds", 120))
    key = _retrieval_key_parts(metadata_filter, question, subtasks, use_hyde, extra_queries)
    cache_body = {
        "contexts": payload.get("contexts", []),
        "queries_used": payload.get("queries_used", []),
        "sources": payload.get("sources", []),
        "total_candidates": payload.get("total_candidates", 0),
    }
    try:
        r.set(key, json.dumps(cache_body, ensure_ascii=False), ex=ttl)
    except Exception:
        pass
