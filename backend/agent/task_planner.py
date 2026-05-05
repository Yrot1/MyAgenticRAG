"""
任务规划器
负责将复杂问题分解为多个可执行的子任务
"""
import os
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from RAG import config_data as config


class TaskPlanner:
    """任务规划器"""
    
    def __init__(self):
        # 使用 ChatGLM
        self.llm = ChatOpenAI(
            model=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base,
            temperature=0.3
        )
        
        # 规划器 Prompt
        self.planner_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个任务规划专家。你的职责是将用户的复杂问题分解为多个简单的子任务。

每个子任务应该是：
1. 具体且可执行
2. 相互独立
3. 按逻辑顺序排列

输出格式：
- 任务 1: [描述]
- 任务 2: [描述]
- ...

如果问题很简单，不需要分解，直接返回：
- 任务 1: [原问题]"""),
            ("user", "请分解以下问题：{question}")
        ])
        
        self.chain = self.planner_prompt | self.llm | StrOutputParser()
    
    def plan(self, question: str) -> list:
        """
        将问题分解为子任务
        
        Args:
            question: 用户问题
            
        Returns:
            子任务列表
        """
        result = self.chain.invoke({"question": question})
        
        # 解析任务列表
        tasks = []
        for line in result.split('\n'):
            line = line.strip()
            if line.startswith('- 任务') or line.startswith('任务'):
                # 提取任务描述
                task_desc = line.split(':', 1)[-1].strip() if ':' in line else line
                if task_desc:
                    tasks.append(task_desc)
        
        return tasks if tasks else [question]
