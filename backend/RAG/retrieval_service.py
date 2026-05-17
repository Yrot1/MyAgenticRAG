"""
统一检索：多查询 / HyDE / 重排序；支持并行构建 query 与并行向量检索
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

from RAG import config_data as config
from RAG.query_rewriter import QueryRewriter
from RAG.reranker import Reranker
from RAG.rag import RagService

from redis_store import get_retrieval_cached, set_retrieval_cached


class RetrievalService:
    def __init__(self, rag_service: Optional[RagService] = None):
        self.rag_service = rag_service or RagService()
        self.query_rewriter = QueryRewriter()
        self.reranker = Reranker()

    def _fetch_per_query_k(self) -> int:
        base = getattr(config, "retrieval_k", None) or config.similarity_threshold
        return max(3, (getattr(config, "rerank_candidate_k", 16) + base) // 3)

    def _retrieve_raw(
        self,
        query: str,
        metadata_filter: Optional[dict],
        k: int,
    ) -> List[Document]:
        return self.rag_service.vector_service.retrieve_documents(
            query,
            k_override=k,
            metadata_filter=metadata_filter,
        )

    def _dedupe_documents(self, docs: List[Document]) -> List[Document]:
        seen = set()
        out: List[Document] = []
        for doc in docs:
            key = (doc.page_content or "")[:200]
            if key and key not in seen:
                seen.add(key)
                out.append(doc)
        return out

    def _use_parallel(self) -> bool:
        return getattr(config, "use_parallel_retrieval", True)

    def _retrieve_many(
        self,
        queries: List[str],
        metadata_filter: Optional[dict],
        per_k: int,
    ) -> List[Document]:
        if not queries:
            return []
        if not self._use_parallel() or len(queries) <= 1:
            all_docs: List[Document] = []
            for q in queries:
                all_docs.extend(self._retrieve_raw(q, metadata_filter, per_k))
            return all_docs

        all_docs: List[Document] = []
        workers = min(8, len(queries))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._retrieve_raw, q, metadata_filter, per_k): q
                for q in queries
            }
            for fut in as_completed(futures):
                q = futures[fut]
                try:
                    all_docs.extend(fut.result())
                except Exception as e:
                    print(f"并行检索失败 [{q[:40]}…]: {e}")
        return all_docs

    def build_queries(
        self,
        question: str,
        subtasks: Optional[List[str]] = None,
        use_hyde: Optional[bool] = None,
    ) -> List[str]:
        """构建多路检索查询（HyDE / 子任务 query 可并行）"""
        queries: List[str] = [question]
        use_hyde_flag = (
            use_hyde if use_hyde is not None else getattr(config, "use_hyde", True)
        )
        use_llm_subtask = getattr(config, "use_llm_subtask_query", False)
        max_sub = getattr(config, "agent_max_subtasks", 4)
        tasks = [
            (t or "").strip()
            for t in (subtasks or [])[:max_sub]
            if (t or "").strip() and (t or "").strip() != question
        ]

        extra_from_tasks: List[str] = []
        hyde_query: Optional[str] = None

        need_pool = self._use_parallel() and (use_hyde_flag or (tasks and use_llm_subtask))
        if need_pool:
            workers = min(8, max(2, len(tasks) + (1 if use_hyde_flag else 0)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures: Dict[Any, str] = {}
                if use_hyde_flag:
                    futures[pool.submit(self.query_rewriter.generate_hyde, question)] = "hyde"
                if use_llm_subtask:
                    for task in tasks:
                        futures[
                            pool.submit(
                                self.query_rewriter.subtask_to_query,
                                task,
                                question,
                            )
                        ] = f"sub:{task}"

                for fut, tag in futures.items():
                    try:
                        result = fut.result()
                        if tag == "hyde" and result and result != question:
                            hyde_query = result
                        elif tag.startswith("sub:") and result:
                            extra_from_tasks.append(result)
                    except Exception as e:
                        print(f"并行 query 构建失败 ({tag}): {e}")
        else:
            if use_hyde_flag:
                hyde_query = self.query_rewriter.generate_hyde(question)
            if use_llm_subtask:
                for task in tasks:
                    extra_from_tasks.append(
                        self.query_rewriter.subtask_to_query(task, question)
                    )
            else:
                extra_from_tasks.extend(t[:150] for t in tasks)

        if hyde_query:
            queries.append(hyde_query)
        for q in extra_from_tasks:
            if q and q not in queries:
                queries.append(q)

        return list(dict.fromkeys(queries))[: max_sub + 3]

    def retrieve(
        self,
        question: str,
        metadata_filter: Optional[dict] = None,
        subtasks: Optional[List[str]] = None,
        use_hyde: Optional[bool] = None,
        extra_queries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        queries = self.build_queries(question, subtasks=subtasks, use_hyde=use_hyde)
        if extra_queries:
            for q in extra_queries:
                if q and q not in queries:
                    queries.append(q)

        cached = get_retrieval_cached(
            metadata_filter,
            question,
            subtasks=subtasks,
            use_hyde=use_hyde,
            extra_queries=extra_queries,
        )
        if cached is not None:
            self.rag_service.last_retrieved_docs = []
            return {
                "contexts": list(cached.get("contexts") or []),
                "documents": [],
                "queries_used": list(cached.get("queries_used") or []),
                "sources": list(cached.get("sources") or []),
                "total_candidates": int(cached.get("total_candidates") or 0),
            }

        per_k = self._fetch_per_query_k()
        all_docs = self._retrieve_many(queries, metadata_filter, per_k)
        all_docs = self._dedupe_documents(all_docs)
        final_k = getattr(config, "retrieval_k", None) or config.similarity_threshold
        ranked = self.reranker.rerank(question, all_docs, top_k=final_k)

        self.rag_service.last_retrieved_docs = ranked
        contexts = [d.page_content for d in ranked if d.page_content]

        sources = []
        for d in ranked:
            meta = d.metadata or {}
            sources.append({
                "source": meta.get("source", ""),
                "preview": (d.page_content or "")[:120],
            })

        payload = {
            "contexts": contexts,
            "documents": ranked,
            "queries_used": queries,
            "sources": sources,
            "total_candidates": len(all_docs),
        }
        set_retrieval_cached(
            metadata_filter,
            question,
            payload,
            subtasks=subtasks,
            use_hyde=use_hyde,
            extra_queries=extra_queries,
        )
        return payload

    def retrieve_with_retry(
        self,
        question: str,
        metadata_filter: Optional[dict] = None,
        subtasks: Optional[List[str]] = None,
        evaluate_fn=None,
    ) -> Dict[str, Any]:
        if not getattr(config, "use_agent_retrieval_eval", False):
            evaluate_fn = None

        max_attempts = getattr(config, "agent_max_retrieval_attempts", 2)
        threshold = getattr(config, "agent_retrieval_threshold", 0.6)

        result = self.retrieve(question, metadata_filter=metadata_filter, subtasks=subtasks)
        attempts = 1
        quality_score = 1.0
        reason = ""

        if evaluate_fn and result["contexts"]:
            ev = evaluate_fn(question, result["contexts"])
            quality_score = float(ev.get("score", 0.5))
            reason = ev.get("reason", "")

        while (
            attempts < max_attempts
            and evaluate_fn
            and quality_score < threshold
        ):
            attempts += 1
            rewritten = self.query_rewriter.rewrite_for_retrieval(
                question, result["contexts"], reason
            )
            retry = self.retrieve(
                question,
                metadata_filter=metadata_filter,
                subtasks=None,
                use_hyde=False,
                extra_queries=[rewritten],
            )
            merged_ctx = list(dict.fromkeys(result["contexts"] + retry["contexts"]))
            final_k = getattr(config, "retrieval_k", None) or config.similarity_threshold
            result["contexts"] = merged_ctx[: final_k + 2]
            result["queries_used"] = list(dict.fromkeys(
                result.get("queries_used", []) + retry.get("queries_used", []) + [rewritten]
            ))
            if evaluate_fn and result["contexts"]:
                ev = evaluate_fn(question, result["contexts"])
                quality_score = float(ev.get("score", 0.5))
                reason = ev.get("reason", "")

        result["quality_score"] = quality_score
        result["attempts"] = attempts
        result["quality_reason"] = reason
        return result
