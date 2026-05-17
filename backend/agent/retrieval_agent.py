"""
检索 Agent：委托统一 RetrievalService
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional

from RAG.rag import RagService
from RAG.retrieval_service import RetrievalService


class RetrievalAgent:
    def __init__(self, rag_service: Optional[RagService] = None):
        self.rag_service = rag_service if rag_service is not None else RagService()
        self.retrieval_service = RetrievalService(self.rag_service)

    def retrieve(self, query: str, k: Optional[int] = None, metadata_filter: Optional[dict] = None) -> dict:
        result = self.retrieval_service.retrieve(
            query,
            metadata_filter=metadata_filter,
        )
        return {
            "success": True,
            "contexts": result.get("contexts", []),
            "query": query,
            "doc_count": len(result.get("contexts", [])),
            "queries_used": result.get("queries_used", []),
        }

    def multi_query_retrieve(
        self,
        queries: List[str],
        k: Optional[int] = None,
        metadata_filter: Optional[dict] = None,
        subtasks: Optional[List[str]] = None,
    ) -> dict:
        primary = queries[0] if queries else ""
        extra = queries[1:] if len(queries) > 1 else None
        result = self.retrieval_service.retrieve(
            primary,
            metadata_filter=metadata_filter,
            subtasks=subtasks,
            extra_queries=extra,
        )
        return {
            "success": True,
            "contexts": result.get("contexts", []),
            "total_retrieved": len(result.get("contexts", [])),
            "queries_used": result.get("queries_used", []),
        }
