"""
评估 Agent
负责评估检索质量和答案质量
"""
import os
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from RAG import config_data as config
import json


class EvaluatorAgent:
    """评估 Agent"""
    
    def __init__(self):
        # 使用 ChatGLM
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.1
        )
        
        # 检索质量评估 Prompt
        self.retrieval_eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个严格的检索质量评估员。评估检索到的上下文是否与问题相关。

评分标准：
- 0.0-0.3: 完全不相关
- 0.4-0.6: 部分相关
- 0.7-1.0: 高度相关

输出 JSON 格式：
{{
    "score": 0.0-1.0,
    "reason": "评估理由"
}}"""),
            ("user", "问题：{question}\n\n检索到的上下文：{contexts}")
        ])
        
        # 答案质量评估 Prompt
        self.answer_eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个答案质量评估员。评估答案是否准确回答了问题。

评分标准：
- 0.0-0.3: 完全没回答问题
- 0.4-0.6: 部分回答
- 0.7-1.0: 完整准确回答

输出 JSON 格式：
{{
    "score": 0.0-1.0,
    "faithfulness": 0.0-1.0,
    "reason": "评估理由"
}}"""),
            ("user", "问题：{question}\n\n答案：{answer}")
        ])
        
        self.retrieval_chain = self.retrieval_eval_prompt | self.llm | StrOutputParser()
        self.answer_chain = self.answer_eval_prompt | self.llm | StrOutputParser()
    
    def evaluate_retrieval(self, question: str, contexts: list) -> dict:
        """
        评估检索质量
        
        Args:
            question: 问题
            contexts: 检索到的上下文列表
            
        Returns:
            评估结果
        """
        if not contexts:
            return {
                "score": 0.0,
                "reason": "没有检索到任何上下文"
            }
        
        try:
            contexts_text = "\n\n".join([f"[{i+1}] {ctx}" for i, ctx in enumerate(contexts)])
            result = self.retrieval_chain.invoke({
                "question": question,
                "contexts": contexts_text
            })
            
            # 解析 JSON
            try:
                eval_result = json.loads(result)
                return eval_result
            except:
                return {
                    "score": 0.5,
                    "reason": result
                }
                
        except Exception as e:
            return {
                "score": 0.5,
                "reason": f"评估失败：{str(e)}"
            }
    
    def evaluate_answer(self, question: str, answer: str) -> dict:
        """
        评估答案质量
        
        Args:
            question: 问题
            answer: 答案
            
        Returns:
            评估结果
        """
        try:
            result = self.answer_chain.invoke({
                "question": question,
                "answer": answer
            })
            
            # 解析 JSON
            try:
                eval_result = json.loads(result)
                return eval_result
            except:
                return {
                    "score": 0.5,
                    "faithfulness": 0.5,
                    "reason": result
                }
                
        except Exception as e:
            return {
                "score": 0.5,
                "faithfulness": 0.5,
                "reason": f"评估失败：{str(e)}"
            }
    
    def should_retrieve_again(self, eval_result: dict, threshold: float = 0.6) -> bool:
        """
        判断是否需要重新检索
        
        Args:
            eval_result: 评估结果
            threshold: 阈值
            
        Returns:
            True 需要重新检索，False 不需要
        """
        score = eval_result.get("score", 0.5)
        return score < threshold
