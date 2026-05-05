from langchain_chroma import Chroma
import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import config_data as config


class VectorStoreService:
    def __init__(self,embedding):
        # 嵌入模型的传入
        self.embedding = embedding
        self.vector_store=Chroma(
            collection_name=config.collection_name,
            embedding_function=self.embedding,     # 嵌入模型
            persist_directory=config.persist_directory,
        )

    def _resolve_k(self, k_override=None):
        if k_override is not None:
            return k_override
        return getattr(config, "retrieval_k", None) or config.similarity_threshold

    def get_retriever(self, k_override=None, metadata_filter=None):
        """返回向量检索器；k 与 Agent / 链式 RAG 保持一致"""
        k = self._resolve_k(k_override)
        fetch_k = max(
            k,
            min(getattr(config, "retrieval_fetch_k", k * 4), 50),
        )
        search_kwargs = {
            "k": k,
            **({"filter": metadata_filter} if metadata_filter else {}),
        }
        if getattr(config, "use_mmr_retriever", False):
            search_kwargs.update({
                "fetch_k": fetch_k,
                "lambda_mult": 0.55,
            })
            return self.vector_store.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs,
            )
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def retrieve_documents(self, query: str, k_override=None, metadata_filter=None):
        """单次检索，供 Agent 与普通 RAG 共用同一套逻辑"""
        retriever = self.get_retriever(k_override=k_override, metadata_filter=metadata_filter)
        return retriever.invoke(query)

if __name__ == '__main__':
    from langchain_community.embeddings import DashScopeEmbeddings
    retriever = VectorStoreService(DashScopeEmbeddings(model="text-embedding-v4")).get_retriever()

    res = retriever.invoke("我的体重120斤,身高178，尺码推荐")
    print(res)
    for idx, doc in enumerate(res):
        print(f"===== 文档 {idx+1} =====")
        print(f"文档内容：{doc.page_content[:100]}")  # 打印前100字
        print(f"文档元数据：{doc.metadata}")  # 现在会显示完整元数据















