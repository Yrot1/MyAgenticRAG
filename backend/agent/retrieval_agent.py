"""
检索 Agent：与普通 RAG 共用同一 VectorStoreService / retriever，避免双实例与 similarity_search 分叉。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List

from RAG.rag import RagService
from RAG import config_data as config


class RetrievalAgent:
    """检索 Agent（底层即 RagService 的 retriever.invoke）"""

    def __init__(self, rag_service: Optional[RagService] = None):
        self.rag_service = rag_service if rag_service is not None else RagService()

    def retrieve(self, query: str, k: Optional[int] = None, metadata_filter: Optional[dict] = None) -> dict:
        """
        执行检索（与 chat_traditional 中 retriever.invoke 一致）

        Args:
            query: 查询文本
            k: 覆盖 config.retrieval_k；None 则用配置
        """
        try:
            docs = self.rag_service.vector_service.retrieve_documents(
                query,
                k_override=k,
                metadata_filter=metadata_filter,
            )
            contexts = [d.page_content for d in docs]
            return {
                "success": True,
                "contexts": contexts,
                "query": query,
                "doc_count": len(contexts),
            }
        except Exception as e:
            return {
                "success": False,
                "contexts": [],
                "error": str(e),
            }

    def multi_query_retrieve(
        self,
        queries: List[str],
        k: Optional[int] = None,
        metadata_filter: Optional[dict] = None,
    ) -> dict:
        """多查询检索并去重（每条查询仍走同一 retriever）"""
        all_contexts = []
        per_k = k
        if per_k is None:
            base = getattr(config, "retrieval_k", None) or config.similarity_threshold
            per_k = max(2, base // 2)

        for query in queries:
            result = self.retrieve(query, k=per_k, metadata_filter=metadata_filter)
            if result["success"]:
                all_contexts.extend(result["contexts"])

        unique_contexts = list(dict.fromkeys(all_contexts))

        return {
            "success": True,
            "contexts": unique_contexts,
            "total_retrieved": len(unique_contexts),
        }
