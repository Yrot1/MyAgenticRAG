"""
检索结果重排序（LLM 打分，无需额外本地模型）
"""
import json
import re
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from RAG import config_data as config


class Reranker:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.0,
        )

    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: Optional[int] = None,
    ) -> List[Document]:
        if not documents:
            return []
        k = top_k or getattr(config, "retrieval_k", None) or config.similarity_threshold
        if len(documents) <= k or not getattr(config, "use_rerank", True):
            return documents[:k]

        numbered = []
        for i, doc in enumerate(documents[: getattr(config, "rerank_candidate_k", 16)]):
            snippet = (doc.page_content or "")[:400]
            src = (doc.metadata or {}).get("source", "")
            numbered.append(f"[{i}] 来源:{src}\n{snippet}")

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是检索重排序器。根据用户问题，为每条文档片段打 0–10 分（10 最相关）。"
                "只输出 JSON 数组，如：[{{\"index\":0,\"score\":9}},{{\"index\":1,\"score\":3}}]",
            ),
            ("user", "问题：{query}\n\n文档片段：\n{docs}"),
        ])
        chain = prompt | self.llm | StrOutputParser()
        try:
            raw = chain.invoke({"query": query, "docs": "\n\n".join(numbered)})
            scores_map = self._parse_scores(raw, len(numbered))
            indexed = list(enumerate(documents[: len(numbered)]))
            indexed.sort(key=lambda x: scores_map.get(x[0], 0), reverse=True)
            return [doc for _, doc in indexed[:k]]
        except Exception as e:
            print(f"rerank 失败，使用向量序: {e}")
            return documents[:k]

    def _parse_scores(self, raw: str, n: int) -> dict:
        scores = {i: 0.0 for i in range(n)}
        try:
            match = re.search(r"\[[\s\S]*\]", raw)
            if match:
                items = json.loads(match.group())
                for item in items:
                    idx = int(item.get("index", -1))
                    if 0 <= idx < n:
                        scores[idx] = float(item.get("score", 0))
                return scores
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        for i in range(n):
            scores[i] = float(n - i)
        return scores
