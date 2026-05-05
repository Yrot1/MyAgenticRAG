"""
答案 Agent
负责整合信息生成最终答案
"""
import os
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from RAG import config_data as config
from typing import List, Dict, Any


class AnswerAgent:
    """答案 Agent"""
    
    def __init__(self):
        # 使用 ChatGLM
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.3
        )
        
        # 答案生成 Prompt
        self.answer_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的知识库助手。请根据提供的参考资料回答用户问题。

要求：
1. 优先使用参考资料中的信息
2. 如果参考资料不足，可以补充你的知识，但要说明
3. 回答简洁、准确、专业
4. 如果资料之间有冲突，指出冲突点
5. 不要编造信息"""),
            ("user", "参考资料：\n{contexts}\n\n用户问题：{question}")
        ])
        
        self.chain = self.answer_prompt | self.llm | StrOutputParser()
    
    def generate(self, question: str, contexts: list) -> str:
        """
        生成答案
        
        Args:
            question: 用户问题
            contexts: 检索到的上下文列表
            
        Returns:
            生成的答案
        """
        if not contexts:
            # 没有上下文，直接回答
            return self._direct_answer(question)
        
        contexts_text = "\n\n".join([f"[资料{i+1}] {ctx}" for i, ctx in enumerate(contexts)])
        
        try:
            answer = self.chain.invoke({
                "question": question,
                "contexts": contexts_text
            })
            return answer
        except Exception as e:
            return f"生成答案时出错：{str(e)}"
    
    def _direct_answer(self, question: str) -> str:
        """
        没有参考资料时直接回答
        
        Args:
            question: 问题
            
        Returns:
            答案
        """
        direct_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的助手。请简洁专业地回答问题。"),
            ("user", "{question}")
        ])
        
        chain = direct_prompt | self.llm | StrOutputParser()
        return chain.invoke({"question": question})
    
    def synthesize(self, question: str, sub_answers: list) -> str:
        """
        综合多个子答案
        
        Args:
            question: 原始问题
            sub_answers: 子任务的答案列表
            
        Returns:
            综合答案
        """
        synthesize_prompt = ChatPromptTemplate.from_messages([
            ("system", """请综合以下多个子问题的答案，形成一个完整、连贯的最终答案。

要求：
1. 整合所有有用信息
2. 消除重复
3. 保持逻辑清晰
4. 直接回答原始问题"""),
            ("user", "原始问题：{question}\n\n子答案：\n{sub_answers}")
        ])
        
        chain = synthesize_prompt | self.llm | StrOutputParser()
        
        sub_answers_text = "\n\n".join([f"[答案{i+1}] {ans}" for i, ans in enumerate(sub_answers)])
        
        return chain.invoke({
            "question": question,
            "sub_answers": sub_answers_text
        })
    
    def regenerate(
        self, 
        question: str, 
        contexts: List[str], 
        feedback: Dict[str, Any]
    ) -> str:
        """
        基于评估反馈重新生成答案
        
        Args:
            question: 用户问题
            contexts: 检索到的上下文
            feedback: 评估反馈 {"score": 0.5, "reason": "..."}
            
        Returns:
            重新生成的答案
        """
        regenerate_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的知识库助手。请根据提供的参考资料和评估反馈重新生成答案。

评估反馈指出了之前答案的不足之处。请：
1. 认真分析评估反馈
2. 优先使用参考资料中的信息
3. 针对反馈中的问题进行改进
4. 回答简洁、准确、专业
5. 不要编造信息"""),
            ("user", "参考资料：\n{contexts}\n\n用户问题：{question}\n\n之前答案的评估反馈：\n{feedback}\n\n请重新生成一个更好的答案：")
        ])
        
        chain = regenerate_prompt | self.llm | StrOutputParser()
        
        contexts_text = "\n\n".join([f"[资料{i+1}] {ctx}" for i, ctx in enumerate(contexts)])
        
        try:
            answer = chain.invoke({
                "question": question,
                "contexts": contexts_text,
                "feedback": feedback.get("reason", "答案质量不高")
            })
            return answer
        except Exception as e:
            return f"重新生成答案时出错：{str(e)}"
