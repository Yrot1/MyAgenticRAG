from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from vector_stores import VectorStoreService
from langchain_community.embeddings import DashScopeEmbeddings
import config_data as config
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.runnables.history import RunnableWithMessageHistory
from file_history_store import get_history
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import ZhipuAIEmbeddings

def print_prompt(prompt):
    # 移除打印，避免 Windows 控制台 GBK 编码问题
    # print("="*20)
    # print(prompt.to_string())
    # print("=" * 20)
    return prompt

class RagService(object):
    def __init__(self):
        self.vector_service = VectorStoreService(
            embedding=ZhipuAIEmbeddings(
                model=config.embedding_model_name,
                api_key=config.llm_api_key
            ),
        )
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system","以我提供的一直参考资料为主，简洁和专业的回答用户问题。"
                          "参考资料:{context}"),
                ("system","并且我提供用户的对话历史纪录，如下："),
                MessagesPlaceholder("history"),
                ("user","请回答用户提问{input}"),
            ]
        )
        self.chat_model=ChatOpenAI(
        temperature=0.6,
        model=config.chat_model_name,
        openai_api_key=config.llm_api_key,
        openai_api_base=config.openai_api_base
    )
        self.chain=self.__get_chain()
        self.last_retrieved_docs = []  # 缓存最后一次检索的文档

    def __get_chain(self):
        """获取最终的执行链"""
        retriever = self.vector_service.get_retriever()
        def format_document(docs:list[Document]):
            if not docs:
                return "无相关参考资料"
            formatted_str=""
            # 缓存检索到的文档
            self.last_retrieved_docs = docs
            for doc in docs:
                formatted_str+=f"文档片段：{doc.page_content}\n文档元数据:{doc.metadata}\n\n"
            return formatted_str

        def temp1(value:dict) -> str:
            return value["input"]

        def temp2(value):
            new_value={}
            new_value["input"]=value["input"]["input"]
            new_value["context"]=value["context"]
            new_value["history"]=value["input"]["history"]
            return new_value


        chain = (
            {
                "input":RunnablePassthrough(),
                "context":RunnableLambda(temp1) |retriever | format_document
            } | RunnableLambda(temp2) | self.prompt_template | print_prompt | self.chat_model | StrOutputParser()
        )
        conversation_chain=RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return conversation_chain

if __name__ == '__main__':
    # session id 配置
    session_config={
        "configurable":{
            "session_id":"user_001"
        }
    }

    res = RagService().chain.invoke({"input":"春天穿什么颜色"},session_config)
    print(res)


















