"""
答案 Agent：星河科技 Nova 售后场景
"""
import os
import sys
from typing import Any, Dict, Generator, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from RAG import config_data as config

AFTER_SALES_SYSTEM = """你是星河科技官方售后智能助手，服务于 Nova 耳机 X1 用户与客服。

要求：
1. 优先依据参考资料（用户手册、保修政策、FAQ、内部话术）回答，并标明依据来源文件名
2. 涉及保修/退换货/进水/指示灯等问题，严格按政策表述，不可承诺文档未写明的权益
3. 资料不足时明确说明「当前知识库未覆盖」，勿编造条款
4. 回答简洁、专业、分点清晰"""


class AnswerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.3,
        )
        self.answer_prompt = ChatPromptTemplate.from_messages([
            ("system", AFTER_SALES_SYSTEM),
            ("user", "参考资料：\n{contexts}\n\n对话历史（如有）：\n{history}\n\n用户问题：{question}"),
        ])
        self.chain = self.answer_prompt | self.llm | StrOutputParser()
        self.stream_chain = self.answer_prompt | self.llm

    def _format_contexts(self, contexts: list) -> str:
        if not contexts:
            return "（无检索到参考资料）"
        return "\n\n".join(f"[资料{i+1}] {ctx}" for i, ctx in enumerate(contexts))

    def _format_history(self, history: Optional[List[Dict[str, Any]]]) -> str:
        if not history:
            return "无"
        lines = []
        for item in history[-10:]:
            role = item.get("role", "")
            content = (item.get("content") or "")[:300]
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines) or "无"

    def generate(
        self,
        question: str,
        contexts: list,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        if not contexts:
            return self._direct_answer(question)
        try:
            return self.chain.invoke({
                "question": question,
                "contexts": self._format_contexts(contexts),
                "history": self._format_history(history),
            })
        except Exception as e:
            return f"生成答案时出错：{str(e)}"

    def stream(
        self,
        question: str,
        contexts: list,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Generator[str, None, None]:
        if not contexts:
            yield self._direct_answer(question)
            return
        try:
            for chunk in self.stream_chain.stream({
                "question": question,
                "contexts": self._format_contexts(contexts),
                "history": self._format_history(history),
            }):
                content = getattr(chunk, "content", None)
                if content:
                    yield content
        except Exception as e:
            yield f"生成答案时出错：{str(e)}"

    def _direct_answer(self, question: str) -> str:
        direct_prompt = ChatPromptTemplate.from_messages([
            ("system", AFTER_SALES_SYSTEM + "\n当前无检索资料，仅可做一般性提示，并建议用户上传手册或联系人工客服。"),
            ("user", "{question}"),
        ])
        chain = direct_prompt | self.llm | StrOutputParser()
        return chain.invoke({"question": question})

    def regenerate(
        self,
        question: str,
        contexts: List[str],
        feedback: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        regenerate_prompt = ChatPromptTemplate.from_messages([
            ("system", AFTER_SALES_SYSTEM + "\n请根据质量评估反馈改进上一轮回答。"),
            (
                "user",
                "参考资料：\n{contexts}\n\n用户问题：{question}\n\n"
                "评估反馈：\n{feedback}\n\n请重新生成更准确的回答：",
            ),
        ])
        chain = regenerate_prompt | self.llm | StrOutputParser()
        reason = feedback.get("reason", "答案质量不足")
        if feedback.get("ragas_scores"):
            reason += f"\nRAGAS: {feedback.get('ragas_scores')}"
        try:
            return chain.invoke({
                "question": question,
                "contexts": self._format_contexts(contexts),
                "feedback": reason,
            })
        except Exception as e:
            return f"重新生成答案时出错：{str(e)}"
