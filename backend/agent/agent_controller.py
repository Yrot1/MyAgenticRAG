"""
Agent 控制器
Agentic RAG 的核心控制器，协调多个 Agent 协作
支持对话历史和思考过程展示
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from RAG import config_data as config
from RAG.rag import RagService

from .task_planner import TaskPlanner
from .retrieval_agent import RetrievalAgent
from .evaluator_agent import EvaluatorAgent
from .answer_agent import AnswerAgent


class AgentController:
    """
    Agent 控制器 - 深度思考模式
    
    工作流程：
    1. TaskPlanner 分解问题（展示用）
    2. 使用与普通 RAG 相同的 retriever，对用户原始问题做一次检索
    3. EvaluatorAgent 评估检索质量
    4. AnswerAgent 生成答案
    5. EvaluatorAgent 评估答案质量
    6. 如需要，触发重新检索或重新生成
    
    特色：
    - 完整的思考过程记录
    - 工具调用日志
    - 对话历史记忆
    """
    
    def __init__(self, rag_service: Optional[RagService] = None):
        self.task_planner = TaskPlanner()
        self.retrieval_agent = RetrievalAgent(rag_service=rag_service)
        self.evaluator_agent = EvaluatorAgent()
        self.answer_agent = AnswerAgent()
        
        # 配置参数
        self.max_retrieval_attempts = 2  # 最大检索次数
        self.retrieval_threshold = 0.6   # 检索质量阈值
        self.answer_threshold = 0.7      # 答案质量阈值
        
        # 对话历史缓存 (按 session_id)
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def execute(
        self, 
        question: str, 
        session_id: str = "default",
        history: Optional[List[Dict[str, Any]]] = None,
        metadata_filter: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的 Agentic RAG 流程（深度思考模式）
        
        Args:
            question: 用户问题
            session_id: 会话 ID
            history: 对话历史列表 [{"role": "user"/"assistant", "content": "..."}]
            
        Returns:
            包含答案、思考过程和元数据的字典
        """
        start_time = datetime.now()
        
        # 初始化或加载对话历史
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        # 使用传入的历史或缓存的历史
        if history:
            self.conversation_history[session_id] = history
        
        # 思考过程记录
        thinking_process = []
        tools_called = []
        
        # ========== Step 1: 任务规划 ==========
        thinking_process.append({
            "stage": "任务规划",
            "status": "running",
            "message": "🤔 正在分析问题，拆解为子任务...",
            "timestamp": datetime.now().isoformat()
        })
        
        tasks = self.task_planner.plan(question)
        
        thinking_process.append({
            "stage": "任务规划",
            "status": "completed",
            "message": f"✅ 任务分解完成，共 {len(tasks)} 个子任务",
            "details": tasks,
            "timestamp": datetime.now().isoformat()
        })
        
        tools_called.append({
            "tool": "TaskPlanner",
            "action": "任务分解",
            "input": question,
            "output": f"{len(tasks)} 个任务",
            "duration_ms": 0
        })
        
        # ========== Step 2: 检索（与用户原始问题一致，同普通 RAG 的 retriever）==========
        thinking_process.append({
            "stage": "信息检索",
            "status": "running",
            "message": "🔍 正在检索知识库（与「快速模式」相同检索器）...",
            "timestamp": datetime.now().isoformat()
        })

        rk = getattr(config, "retrieval_k", None) or config.similarity_threshold
        retrieval_result = self._retrieve_with_evaluation(question, k=rk, metadata_filter=metadata_filter)
        all_contexts = list(dict.fromkeys(retrieval_result["contexts"]))

        retrieval_logs = [{
            "task": question,
            "contexts_count": len(all_contexts),
            "quality_score": retrieval_result.get("quality_score", 0),
            "attempts": retrieval_result.get("attempts", 1),
            "planned_subtasks": tasks,
        }]

        thinking_process.append({
            "stage": "信息检索",
            "status": "completed",
            "message": f"✅ 检索完成，共 {len(all_contexts)} 条上下文（规划子任务 {len(tasks)} 个，仅供拆解展示）",
            "details": {
                "quality_score": retrieval_result.get("quality_score", 0),
                "attempts": retrieval_result.get("attempts", 1),
                "subtasks": tasks,
            },
            "timestamp": datetime.now().isoformat()
        })

        tools_called.append({
            "tool": "RetrievalAgent",
            "action": "向量检索（RAG retriever）",
            "input": question,
            "output": f"{len(all_contexts)} 条文档",
            "metadata": {
                "quality_score": retrieval_result.get("quality_score", 0),
                "attempts": retrieval_result.get("attempts", 1),
                "k": rk,
            },
            "duration_ms": 0
        })

        thinking_process.append({
            "stage": "信息整合",
            "status": "completed",
            "message": f"📚 信息整合完成，共 {len(all_contexts)} 条唯一上下文",
            "timestamp": datetime.now().isoformat()
        })
        
        # ========== Step 3: 生成答案 ==========
        thinking_process.append({
            "stage": "答案生成",
            "status": "running",
            "message": "✍️  正在基于检索到的信息生成答案...",
            "timestamp": datetime.now().isoformat()
        })
        
        answer = self.answer_agent.generate(question, all_contexts)
        
        thinking_process.append({
            "stage": "答案生成",
            "status": "completed",
            "message": "✅ 答案生成完成",
            "timestamp": datetime.now().isoformat()
        })
        
        tools_called.append({
            "tool": "AnswerAgent",
            "action": "答案生成",
            "input": f"基于 {len(all_contexts)} 条上下文",
            "output": f"答案长度：{len(answer)} 字符",
            "duration_ms": 0
        })
        
        # ========== Step 4: 评估答案质量 ==========
        thinking_process.append({
            "stage": "质量评估",
            "status": "running",
            "message": "🎯 正在评估答案质量...",
            "timestamp": datetime.now().isoformat()
        })
        
        answer_eval = self.evaluator_agent.evaluate_answer(question, answer)
        
        tools_called.append({
            "tool": "EvaluatorAgent",
            "action": "答案评估",
            "input": answer[:100] + "...",
            "output": f"得分：{answer_eval.get('score', 0):.2f}",
            "metadata": answer_eval,
            "duration_ms": 0
        })
        
        # ========== Step 5: 如果答案质量低，尝试重新生成 ==========
        if answer_eval.get("score", 0) < self.answer_threshold:
            thinking_process.append({
                "stage": "质量评估",
                "status": "warning",
                "message": f"⚠️  答案质量较低 (得分：{answer_eval.get('score', 0):.2f})，正在重新生成...",
                "details": answer_eval.get("reason", ""),
                "timestamp": datetime.now().isoformat()
            })
            
            answer = self._regenerate_answer(question, all_contexts, answer_eval)
            
            # 重新评估
            answer_eval = self.evaluator_agent.evaluate_answer(question, answer)
            
            thinking_process.append({
                "stage": "重新生成",
                "status": "completed",
                "message": f"✅ 重新生成完成，新得分：{answer_eval.get('score', 0):.2f}",
                "timestamp": datetime.now().isoformat()
            })
            
            tools_called.append({
                "tool": "AnswerAgent",
                "action": "答案重新生成",
                "input": f"基于评估反馈：{answer_eval.get('reason', '')[:50]}...",
                "output": f"新答案长度：{len(answer)} 字符",
                "duration_ms": 0
            })
        else:
            thinking_process.append({
                "stage": "质量评估",
                "status": "success",
                "message": f"✅ 答案质量良好 (得分：{answer_eval.get('score', 0):.2f})",
                "details": answer_eval.get("reason", ""),
                "timestamp": datetime.now().isoformat()
            })
        
        # 计算总耗时
        end_time = datetime.now()
        total_duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # 更新对话历史
        self.conversation_history[session_id].append({
            "role": "user",
            "content": question,
            "timestamp": start_time.isoformat()
        })
        self.conversation_history[session_id].append({
            "role": "assistant",
            "content": answer,
            "timestamp": end_time.isoformat()
        })
        
        # ========== 返回完整结果 ==========
        return {
            "answer": answer,
            "contexts": all_contexts,
            "tasks": tasks,
            "retrieval_logs": retrieval_logs,
            "thinking_process": thinking_process,  # 完整思考过程
            "tools_called": tools_called,          # 工具调用日志
            "evaluation": {
                "answer_score": answer_eval.get("score", 0),
                "faithfulness": answer_eval.get("faithfulness", 0),
                "reason": answer_eval.get("reason", "")
            },
            "metadata": {
                "total_contexts": len(all_contexts),
                "total_tasks": len(tasks),
                "total_duration_ms": total_duration_ms,
                "session_id": session_id,
                "model": "glm-4.5-air",
                "mode": "agentic_rag"
            },
            "conversation_history": self.conversation_history[session_id].copy()
        }
    
    def _retrieve_with_evaluation(
        self,
        query: str,
        k: Optional[int] = None,
        metadata_filter: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        带评估的检索流程
        
        Returns:
            {
                "contexts": [...],
                "quality_score": 0.0-1.0,
                "attempts": 1
            }
        """
        attempts = 0
        contexts = []
        quality_score = 0.0
        
        while attempts < self.max_retrieval_attempts:
            attempts += 1
            
            # 执行检索
            result = self.retrieval_agent.retrieve(query, k=k, metadata_filter=metadata_filter)
            
            if not result.get("success"):
                continue
            
            contexts = result.get("contexts", [])
            
            if not contexts:
                continue
            
            # 评估检索质量
            eval_result = self.evaluator_agent.evaluate_retrieval(query, contexts)
            quality_score = eval_result.get("score", 0)
            
            # 如果质量达标，提前结束
            if quality_score >= self.retrieval_threshold:
                break
        
        return {
            "contexts": contexts,
            "quality_score": quality_score,
            "attempts": attempts
        }
    
    def _regenerate_answer(
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
            feedback: 评估反馈
            
        Returns:
            重新生成的答案
        """
        return self.answer_agent.regenerate(question, contexts, feedback)
    
    def clear_history(self, session_id: str) -> bool:
        """清除指定会话的历史记录"""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
            return True
        return False
    
    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的历史记录"""
        return self.conversation_history.get(session_id, [])
