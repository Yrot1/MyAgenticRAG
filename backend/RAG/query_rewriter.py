"""
查询改写与 HyDE（假设性文档嵌入）
"""
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from RAG import config_data as config


class QueryRewriter:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.2,
        )

    def generate_hyde(self, question: str) -> str:
        """生成假设性答案段落，用于辅助向量检索"""
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是星河科技 Nova 耳机售后知识库助手。根据用户问题，写一段可能出现在"
                "官方用户手册、保修政策或 FAQ 中的简短说明（80–200 字），只输出段落正文，不要标题。",
            ),
            ("user", "{question}"),
        ])
        chain = prompt | self.llm | StrOutputParser()
        try:
            text = chain.invoke({"question": question}).strip()
            return text[:500] if text else question
        except Exception:
            return question

    def rewrite_for_retrieval(
        self,
        question: str,
        contexts: list,
        reason: str = "",
    ) -> str:
        """检索质量不足时改写查询"""
        ctx_preview = "\n".join(contexts[:3])[:800] if contexts else "（无检索结果）"
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "将用户问题改写为更适合在售后知识库中检索的短查询（一句话）。"
                "只输出改写后的查询，不要解释。",
            ),
            (
                "user",
                "原问题：{question}\n"
                "上次检索片段摘要：{contexts}\n"
                "评估说明：{reason}\n"
                "请输出改写查询：",
            ),
        ])
        chain = prompt | self.llm | StrOutputParser()
        try:
            out = chain.invoke({
                "question": question,
                "contexts": ctx_preview,
                "reason": reason or "检索结果与问题相关性不足",
            }).strip()
            out = re.sub(r'^["\']|["\']$', "", out)
            return out[:200] if out else question
        except Exception:
            return question

    def subtask_to_query(self, subtask: str, original_question: str) -> str:
        """将规划子任务转为检索查询句"""
        if len(subtask) > 80:
            return subtask[:80]
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "把子任务改写成一条适合向量检索的短问句，保留产品/政策关键词。只输出问句。",
            ),
            ("user", "用户总问题：{question}\n子任务：{subtask}"),
        ])
        chain = prompt | self.llm | StrOutputParser()
        try:
            q = chain.invoke({"question": original_question, "subtask": subtask}).strip()
            return q[:150] if q else subtask
        except Exception:
            return subtask
