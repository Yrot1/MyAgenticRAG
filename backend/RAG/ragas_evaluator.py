"""
RAGAS 评估模块
用于评估 RAG 系统的回答质量
"""
import os
import sys
from typing import List, Dict, Any

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from datasets import Dataset
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import (
    faithfulness,  # 忠实度：答案是否基于检索内容
    answer_relevancy,  # 答案相关性：答案是否与问题相关
    answer_similarity,  # 答案相似度（可选，需要标准答案）
)
import config_data as config

# 不使用需要标准答案的指标
# context_precision, context_recall, context_entity_recall, answer_correctness 都需要 reference


class RagasEvaluator:
    def __init__(self):
        """
        初始化 RAGAS 评估器
        注意：需要使用 OpenAI API 或者兼容的 API
        """
        # 使用智谱 AI 的 API（兼容 OpenAI 格式）
        self.llm = ChatOpenAI(
            model_name=config.chat_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base
        )
        
        self.embeddings = OpenAIEmbeddings(
            model=config.embedding_model_name,
            openai_api_key=config.llm_api_key,
            openai_api_base=config.openai_api_base
        )
        
        # 配置评估指标（不需要标准答案）
        self.metrics = [
            faithfulness,  # 忠实度
            answer_relevancy,  # 答案相关性
        ]
    
    def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: str = None
    ) -> Dict[str, Any]:
        """
        评估单个问答对
        
        Args:
            question: 用户问题
            answer: 模型回答
            contexts: 检索到的上下文列表
            ground_truth: 标准答案（可选，用于计算更精确的指标）
        
        Returns:
            评估结果字典
        """
        # 准备数据
        data_sample = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }
        
        if ground_truth:
            data_sample["ground_truth"] = [ground_truth]
        
        # 转换为 Dataset
        dataset = Dataset.from_dict(data_sample)
        
        # 执行评估
        print(f"\n=== RAGAS 评估开始 ===")
        print(f"问题：{question}")
        print(f"答案：{answer[:100]}...")
        print(f"上下文数量：{len(contexts)}")
        print(f"第一个上下文：{contexts[0][:100]}...")
        
        results = evaluate(
            dataset=dataset,
            llm=self.llm,
            embeddings=self.embeddings,
            metrics=self.metrics,
            show_progress=True,
        )
        
        # 提取分数（RAGAS 返回的是列表，需要取第一个元素）
        scores = {}
        for metric in self.metrics:
            metric_name = metric.name if hasattr(metric, 'name') else metric.__name__
            result_value = results[metric_name]
            # 如果是列表，取第一个元素
            if isinstance(result_value, (list, tuple)):
                scores[metric_name] = float(result_value[0]) if len(result_value) > 0 else 0.0
            else:
                scores[metric_name] = float(result_value)
            
            print(f"{metric_name}: {scores[metric_name]:.4f}")
        
        # 计算综合分数
        valid_scores = [v for v in scores.values() if v is not None and not isinstance(v, list)]
        scores["overall_score"] = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        
        print(f"综合评分：{scores['overall_score']:.4f}")
        print(f"=== RAGAS 评估结束 ===\n")
        
        return scores
    
    def evaluate_batch(
        self,
        questions: List[str],
        answers: List[str],
        contexts_list: List[List[str]],
        ground_truths: List[str] = None
    ) -> Dict[str, Any]:
        """
        批量评估多个问答对
        
        Args:
            questions: 问题列表
            answers: 答案列表
            contexts_list: 检索到的上下文列表的列表
            ground_truths: 标准答案列表（可选）
        
        Returns:
            评估结果统计
        """
        # 准备数据
        data_sample = {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
        }
        
        if ground_truths:
            data_sample["ground_truth"] = ground_truths
        
        dataset = Dataset.from_dict(data_sample)
        
        # 执行评估
        results = evaluate(
            dataset=dataset,
            llm=self.llm,
            embeddings=self.embeddings,
            metrics=self.metrics,
        )
        
        # 返回详细结果
        metrics_result = {}
        for metric in self.metrics:
            metric_name = metric.name if hasattr(metric, 'name') else metric.__name__
            result_value = results[metric_name]
            # 如果是列表，取平均值
            if isinstance(result_value, (list, tuple)):
                metrics_result[metric_name] = float(sum(result_value) / len(result_value)) if result_value else 0.0
            else:
                metrics_result[metric_name] = float(result_value)
        
        # 计算综合分数
        valid_scores = [v for v in metrics_result.values() if not isinstance(v, list)]
        overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        
        return {
            "metrics": metrics_result,
            "overall_score": overall,
            "total_samples": len(questions),
        }
    
    def get_evaluation_interpretation(self, scores: Dict[str, float]) -> str:
        """
        获取评估分数的解释
        
        Args:
            scores: 评估分数字典
        
        Returns:
            解释文本
        """
        interpretation = []
        
        overall = scores.get("overall_score", 0)
        if overall >= 0.8:
            interpretation.append("✅ 整体质量优秀")
        elif overall >= 0.6:
            interpretation.append("⚠️ 整体质量良好，有改进空间")
        else:
            interpretation.append("❌ 整体质量需要改进")
        
        if "faithfulness" in scores and scores["faithfulness"]:
            faithfulness_score = scores["faithfulness"]
            if faithfulness_score >= 0.8:
                interpretation.append("✅ 忠实度高：答案完全基于检索内容，没有幻觉")
            elif faithfulness_score >= 0.6:
                interpretation.append("⚠️ 忠实度中等：答案大部分基于检索内容")
            else:
                interpretation.append("❌ 忠实度低：答案可能包含未检索到的信息")
        
        if "answer_relevancy" in scores and scores["answer_relevancy"]:
            relevancy_score = scores["answer_relevancy"]
            if relevancy_score >= 0.7:
                interpretation.append("✅ 相关性好：答案与问题高度相关")
            elif relevancy_score >= 0.5:
                interpretation.append("⚠️ 相关性中等：答案基本相关，但可能不够精准")
            else:
                interpretation.append("❌ 相关性差：答案可能偏离问题")
        
        return "\n".join(interpretation)


# 使用示例
if __name__ == "__main__":
    # 创建评估器
    evaluator = RagasEvaluator()
    
    # 示例数据
    question = "知识库中有哪些关于面试的资料？"
    answer = "知识库中包含面试题汇编、面试技巧指南等资料..."
    contexts = [
        "面试题汇编文档包含了常见的技术面试问题...",
        "面试技巧指南介绍了如何准备面试..."
    ]
    
    # 评估
    scores = evaluator.evaluate_single(
        question=question,
        answer=answer,
        contexts=contexts
    )
    
    print("评估结果：")
    for metric, score in scores.items():
        print(f"{metric}: {score:.4f}")
    
    print("\n评估解读：")
    print(evaluator.get_evaluation_interpretation(scores))
