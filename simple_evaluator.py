"""
简单的 RAG 评估模块
使用更直接的方式评估答案质量
"""
import re
from typing import List, Dict
from difflib import SequenceMatcher


class SimpleRAGEvaluator:
    """
    简单 RAG 评估器
    通过对比答案和检索内容的相似度来评估
    """
    
    @staticmethod
    def calculate_text_similarity(text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（0-1 之间）
        """
        # 去除标点符号和空白字符
        def normalize(text):
            text = text.lower()
            text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
            return text
        
        norm1 = normalize(text1)
        norm2 = normalize(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @staticmethod
    def extract_key_sentences(text: str, max_sentences: int = 5) -> List[str]:
        """
        提取文本中的关键句子
        """
        # 按句号、问号、感叹号分割
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 返回最重要的几句（这里简单返回前几句）
        return sentences[:max_sentences]
    
    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: str = None
    ) -> Dict:
        """
        评估答案质量
        
        Args:
            question: 用户问题
            answer: 模型答案
            contexts: 检索到的上下文列表
            ground_truth: 标准答案（可选）
        
        Returns:
            评估结果字典
        """
        # 1. 计算答案与上下文的相似度
        context_similarity_scores = []
        for context in contexts:
            sim = self.calculate_text_similarity(answer, context)
            context_similarity_scores.append(sim)
        
        avg_context_similarity = sum(context_similarity_scores) / len(context_similarity_scores) if context_similarity_scores else 0
        
        # 2. 检查答案是否包含上下文中的关键信息
        key_info_coverage = self.check_key_info_coverage(answer, contexts)
        
        # 3. 如果有标准答案，计算与标准答案的相似度
        ground_truth_similarity = None
        if ground_truth:
            ground_truth_similarity = self.calculate_text_similarity(answer, ground_truth)
        
        # 4. 计算答案相关性（基于问题和答案的关键词重叠）
        relevance_score = self.calculate_relevance(question, answer)
        
        # 5. 综合评分
        scores = {
            "context_similarity": round(avg_context_similarity, 3),  # 与上下文的相似度
            "key_info_coverage": round(key_info_coverage, 3),  # 关键信息覆盖率
            "relevance": round(relevance_score, 3),  # 问题相关性
        }
        
        if ground_truth_similarity:
            scores["ground_truth_similarity"] = round(ground_truth_similarity, 3)
        
        # 计算综合分数（加权平均）
        if ground_truth_similarity:
            overall = (avg_context_similarity * 0.3 + key_info_coverage * 0.3 + 
                      relevance_score * 0.2 + ground_truth_similarity * 0.2)
        else:
            overall = (avg_context_similarity * 0.4 + key_info_coverage * 0.3 + 
                      relevance_score * 0.3)
        
        scores["overall_score"] = round(overall, 3)
        
        return {
            "scores": scores,
            "interpretation": self.get_interpretation(scores)
        }
    
    def check_key_info_coverage(self, answer: str, contexts: List[str]) -> float:
        """
        检查答案是否覆盖了上下文中的关键信息
        使用更智能的方式：提取关键信息点，而不是完整句子
        """
        if not contexts:
            return 0.0
        
        # 合并所有上下文
        full_context = "\n".join(contexts)
        
        # 提取关键信息点（去除空行、标题等）
        lines = full_context.split('\n')
        key_info_lines = []
        for line in lines:
            line = line.strip()
            # 跳过空行、标题（以#开头）、太短的行
            if not line or line.startswith('#') or len(line) < 10:
                continue
            key_info_lines.append(line)
        
        if not key_info_lines:
            return 0.0
        
        # 检查答案是否包含这些关键信息
        covered_count = 0
        for info_line in key_info_lines:
            # 如果答案包含这个信息行，或者高度相似
            if info_line in answer:
                covered_count += 1
            elif self.calculate_text_similarity(info_line, answer) > 0.5:
                covered_count += 0.5  # 部分覆盖
        
        return min(covered_count / len(key_info_lines), 1.0)
    
    def calculate_relevance(self, question: str, answer: str) -> float:
        """
        计算答案与问题的相关性
        基于关键词重叠度
        """
        # 提取问题中的关键词（简单实现：去除停用词）
        stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', 
                     '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', 
                     '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '什么'}
        
        def extract_keywords(text):
            # 简单分词（按字符）
            words = list(text)
            # 过滤停用词和标点
            keywords = [w for w in words if w not in stop_words and re.match(r'[\w\u4e00-\u9fff]', w)]
            return set(keywords)
        
        question_keywords = extract_keywords(question)
        answer_keywords = extract_keywords(answer)
        
        if not question_keywords:
            return 0.0
        
        # 计算关键词重叠度
        overlap = question_keywords & answer_keywords
        relevance = len(overlap) / len(question_keywords)
        
        return min(relevance * 2, 1.0)  # 放大相关性分数
    
    def get_interpretation(self, scores: Dict) -> str:
        """
        获取评估解读
        """
        interpretation = []
        
        overall = scores.get("overall_score", 0)
        if overall >= 0.8:
            interpretation.append("[优秀] 整体质量优秀")
        elif overall >= 0.6:
            interpretation.append("[良好] 整体质量良好，有改进空间")
        else:
            interpretation.append("[需改进] 整体质量需要改进")
        
        # 上下文相似度
        context_sim = scores.get("context_similarity", 0)
        if context_sim >= 0.7:
            interpretation.append("[一致] 与知识库内容高度一致")
        elif context_sim >= 0.4:
            interpretation.append("[部分一致] 与知识库内容部分一致")
        else:
            interpretation.append("[不一致] 与知识库内容一致性较低")
        
        # 关键信息覆盖率
        coverage = scores.get("key_info_coverage", 0)
        if coverage >= 0.7:
            interpretation.append("[覆盖完整] 关键信息覆盖完整")
        elif coverage >= 0.4:
            interpretation.append("[覆盖不足] 关键信息覆盖不足")
        else:
            interpretation.append("[缺失较多] 关键信息缺失较多")
        
        # 相关性
        relevance = scores.get("relevance", 0)
        if relevance >= 0.7:
            interpretation.append("[高度相关] 答案与问题高度相关")
        elif relevance >= 0.4:
            interpretation.append("[部分相关] 答案与问题部分相关")
        else:
            interpretation.append("[相关性低] 答案与问题相关性较低")
        
        return "\n".join(interpretation)


# 使用示例
if __name__ == "__main__":
    evaluator = SimpleRAGEvaluator()
    
    question = "蔡徐坤是谁"
    answer = "蔡徐坤是 1998 年 8 月 2 日出生于浙江温州的内地男歌手、音乐人、制作人。"
    contexts = [
        "蔡徐坤，1998 年 8 月 2 日出生于浙江温州，内地男歌手、音乐人、制作人。",
        "2018 年通过选秀节目出道，以 C 位身份成团开启演艺事业。"
    ]
    
    result = evaluator.evaluate(question, answer, contexts)
    
    print("评估结果：")
    for metric, score in result["scores"].items():
        print(f"{metric}: {score}")
    
    print("\n评估解读：")
    print(result["interpretation"])
