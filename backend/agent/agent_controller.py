"""
Agent 控制器：并行检索、可关闭评估以加速
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from RAG import config_data as config
from RAG.rag import RagService
from RAG.retrieval_service import RetrievalService
from RAG.ragas_evaluator import RagasEvaluator
from redis_store import (
    append_session_turn,
    clear_session_history,
    get_session_history,
    set_session_history,
)

from .task_planner import TaskPlanner
from .evaluator_agent import EvaluatorAgent
from .answer_agent import AnswerAgent


class AgentController:
    def __init__(
        self,
        rag_service: Optional[RagService] = None,
        ragas_evaluator: Optional[RagasEvaluator] = None,
    ):
        self.rag_service = rag_service or RagService()
        self.retrieval_service = RetrievalService(self.rag_service)
        self.task_planner = TaskPlanner()
        self.evaluator_agent = EvaluatorAgent()
        self.answer_agent = AnswerAgent()
        self.ragas_evaluator = ragas_evaluator or RagasEvaluator()

        self.max_retrieval_attempts = getattr(config, "agent_max_retrieval_attempts", 2)
        self.retrieval_threshold = getattr(config, "agent_retrieval_threshold", 0.6)
        self.answer_threshold = getattr(config, "agent_answer_threshold", 0.65)
        self.ragas_faith_threshold = getattr(config, "ragas_faithfulness_threshold", 0.55)

    def _should_eval_retrieval(self) -> bool:
        return getattr(config, "use_agent_retrieval_eval", False)

    def _should_eval_answer(self) -> bool:
        if getattr(config, "use_ragas_in_agent", False):
            return True
        return getattr(config, "use_agent_answer_eval", False)

    def _evaluate_retrieval(self, question: str, contexts: list) -> dict:
        return self.evaluator_agent.evaluate_retrieval(question, contexts)

    def _evaluate_answer(self, question: str, answer: str, contexts: list) -> dict:
        if getattr(config, "use_ragas_in_agent", False):
            try:
                scores = self.ragas_evaluator.evaluate_single(
                    question=question,
                    answer=answer,
                    contexts=contexts or ["无检索上下文"],
                )
                faith = float(scores.get("faithfulness") or 0)
                rel = float(scores.get("answer_relevancy") or 0)
                overall = float(scores.get("overall_score") or (faith + rel) / 2)
                return {
                    "score": overall,
                    "faithfulness": faith,
                    "answer_relevancy": rel,
                    "reason": self.ragas_evaluator.get_evaluation_interpretation(scores),
                    "ragas_scores": scores,
                    "source": "ragas",
                }
            except Exception as e:
                print(f"RAGAS 评估失败，回退 LLM 评估: {e}")
        return self.evaluator_agent.evaluate_answer(question, answer)

    def _merge_retrieval(self, primary: dict, extra: dict) -> dict:
        """合并两次检索结果（保留 primary 的元数据，合并 contexts）"""
        ctx = list(dict.fromkeys(
            (primary.get("contexts") or []) + (extra.get("contexts") or [])
        ))
        final_k = getattr(config, "retrieval_k", None) or config.similarity_threshold
        merged = {**primary, **extra}
        merged["contexts"] = ctx[: final_k + 2]
        merged["queries_used"] = list(dict.fromkeys(
            (primary.get("queries_used") or []) + (extra.get("queries_used") or [])
        ))
        merged["total_candidates"] = (
            (primary.get("total_candidates") or 0) + (extra.get("total_candidates") or 0)
        )
        return merged

    def _plan_and_retrieve(
        self,
        question: str,
        metadata_filter: Optional[dict],
    ) -> tuple:
        """规划与「原问题检索」并行；有子任务时再补一轮检索并合并"""
        eval_fn = self._evaluate_retrieval if self._should_eval_retrieval() else None

        def do_plan():
            return self.task_planner.plan(question)

        def do_retrieve(tasks: Optional[List[str]]):
            return self.retrieval_service.retrieve_with_retry(
                question,
                metadata_filter=metadata_filter,
                subtasks=tasks,
                evaluate_fn=eval_fn,
            )

        if not getattr(config, "use_parallel_retrieval", True):
            tasks = do_plan()
            return tasks, do_retrieve(tasks)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_plan = pool.submit(do_plan)
            fut_base = pool.submit(do_retrieve, None)
            tasks = fut_plan.result()
            base_result = fut_base.result()

        meaningful = [
            t for t in tasks
            if (t or "").strip() and (t or "").strip() != question
        ]
        if not meaningful:
            return tasks, base_result

        extra_result = do_retrieve(tasks)
        return tasks, self._merge_retrieval(base_result, extra_result)

    def execute(
        self,
        question: str,
        session_id: str = "default",
        history: Optional[List[Dict[str, Any]]] = None,
        metadata_filter: Optional[dict] = None,
    ) -> Dict[str, Any]:
        final = None
        for event in self.execute_stream(
            question, session_id, history, metadata_filter
        ):
            if event.get("type") == "final":
                final = event["payload"]
        return final or {"answer": "", "contexts": [], "thinking_process": []}

    def execute_stream(
        self,
        question: str,
        session_id: str = "default",
        history: Optional[List[Dict[str, Any]]] = None,
        metadata_filter: Optional[dict] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        start_time = datetime.now()
        if history:
            set_session_history(session_id, history)
            effective_history = history
        else:
            effective_history = get_session_history(session_id)

        thinking_process: List[Dict[str, Any]] = []
        tools_called: List[Dict[str, Any]] = []

        def emit_thinking(stage: str, status: str, message: str, details=None):
            step = {
                "stage": stage,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
            if details is not None:
                step["details"] = details
            thinking_process.append(step)
            yield {"type": "thinking", "thinking_process": thinking_process.copy()}

        yield from emit_thinking("任务规划", "running", "正在分析问题并拆解子任务…")
        yield from emit_thinking(
            "信息检索",
            "running",
            "并行检索中（多路 query + 向量检索）…",
        )

        tasks, retrieval_result = self._plan_and_retrieve(question, metadata_filter)

        yield from emit_thinking(
            "任务规划",
            "completed",
            f"任务分解完成，共 {len(tasks)} 个子任务",
            tasks,
        )
        tools_called.append({
            "tool": "TaskPlanner",
            "action": "任务分解",
            "input": question,
            "output": f"{len(tasks)} 个子任务",
            "duration_ms": 0,
        })

        all_contexts = retrieval_result.get("contexts", [])
        queries_used = retrieval_result.get("queries_used", [])

        retrieval_logs = [{
            "queries": queries_used,
            "contexts_count": len(all_contexts),
            "quality_score": retrieval_result.get("quality_score", 0),
            "attempts": retrieval_result.get("attempts", 1),
            "planned_subtasks": tasks,
            "total_candidates": retrieval_result.get("total_candidates", 0),
        }]

        yield from emit_thinking(
            "信息检索",
            "completed",
            f"检索完成：{len(queries_used)} 条查询 → {len(all_contexts)} 条上下文",
            {
                "queries_used": queries_used,
                "quality_score": retrieval_result.get("quality_score", 0),
                "subtasks": tasks,
            },
        )
        tools_called.append({
            "tool": "RetrievalService",
            "action": "parallel_multi_query",
            "input": ", ".join(queries_used[:5]),
            "output": f"{len(all_contexts)} 条文档",
            "metadata": retrieval_logs[0],
            "duration_ms": 0,
        })

        yield from emit_thinking("答案生成", "running", "正在流式生成回答…")
        answer_parts: List[str] = []
        for token in self.answer_agent.stream(question, all_contexts, history=effective_history):
            answer_parts.append(token)
            yield {"type": "content", "content": token}

        answer = "".join(answer_parts)
        if not answer.strip() and all_contexts:
            answer = self.answer_agent.generate(question, all_contexts, history=effective_history)
        yield from emit_thinking("答案生成", "completed", "答案生成完成")

        answer_eval: Dict[str, Any] = {
            "score": 1.0,
            "faithfulness": 1.0,
            "reason": "已跳过答案评估（加速）",
            "source": "skipped",
        }
        need_regen = False

        if self._should_eval_answer():
            yield from emit_thinking("质量评估", "running", "正在评估答案质量…")
            answer_eval = self._evaluate_answer(question, answer, all_contexts)
            faith = float(answer_eval.get("faithfulness") or answer_eval.get("score") or 0)
            need_regen = (
                answer_eval.get("score", 0) < self.answer_threshold
                or faith < self.ragas_faith_threshold
            )
            if need_regen:
                yield from emit_thinking(
                    "质量评估",
                    "warning",
                    f"质量未达标，正在重新生成…",
                    answer_eval.get("reason", ""),
                )
                answer = self.answer_agent.regenerate(
                    question, all_contexts, answer_eval, history=effective_history
                )
                yield {"type": "content_replace", "content": answer}
                answer_eval = self._evaluate_answer(question, answer, all_contexts)
                yield from emit_thinking(
                    "重新生成",
                    "completed",
                    f"重新生成完成，得分 {answer_eval.get('score', 0):.2f}",
                )
            else:
                yield from emit_thinking(
                    "质量评估",
                    "success",
                    f"质量达标（{answer_eval.get('score', 0):.2f}）",
                    answer_eval.get("reason", ""),
                )
        else:
            yield from emit_thinking("质量评估", "completed", "已跳过（加速模式）")

        end_time = datetime.now()
        total_duration_ms = int((end_time - start_time).total_seconds() * 1000)

        append_session_turn(
            session_id,
            {
                "role": "user",
                "content": question,
                "timestamp": start_time.isoformat(),
            },
            {
                "role": "assistant",
                "content": answer,
                "timestamp": end_time.isoformat(),
            },
        )

        payload = {
            "answer": answer,
            "contexts": all_contexts,
            "tasks": tasks,
            "retrieval_logs": retrieval_logs,
            "thinking_process": thinking_process,
            "tools_called": tools_called,
            "evaluation": {
                "answer_score": answer_eval.get("score", 0),
                "faithfulness": answer_eval.get("faithfulness", 0),
                "answer_relevancy": answer_eval.get("answer_relevancy", 0),
                "reason": answer_eval.get("reason", ""),
                "source": answer_eval.get("source", "unknown"),
                "ragas_scores": answer_eval.get("ragas_scores"),
            },
            "metadata": {
                "total_contexts": len(all_contexts),
                "total_tasks": len(tasks),
                "queries_used": queries_used,
                "total_duration_ms": total_duration_ms,
                "session_id": session_id,
                "model": config.chat_model_name,
                "mode": "agentic_rag",
                "scene": "xinghe_after_sales",
            },
            "conversation_history": get_session_history(session_id),
        }
        yield {"type": "final", "payload": payload}

    def clear_history(self, session_id: str) -> bool:
        existed = bool(get_session_history(session_id))
        clear_session_history(session_id)
        return existed

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        return get_session_history(session_id)
