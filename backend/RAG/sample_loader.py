"""
导入 backend/RAG/data 下的星河科技演示语料
"""
import os
from typing import Dict, List

from RAG import config_data as config
from RAG.knowledge_base import KnowledgeBaseService


def list_sample_files() -> List[str]:
    data_dir = getattr(config, "sample_data_dir", None)
    if not data_dir or not os.path.isdir(data_dir):
        return []
    files = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if os.path.isfile(path) and name.lower().endswith((".md", ".txt", ".markdown")):
            files.append(path)
    return files


def load_samples_for_user(user_id: int, kb_service=None) -> Dict:
    kb = kb_service or KnowledgeBaseService()
    paths = list_sample_files()
    if not paths:
        return {
            "status": "error",
            "message": f"未找到演示语料目录：{getattr(config, 'sample_data_dir', '')}",
            "loaded": [],
            "skipped": [],
        }

    loaded = []
    skipped = []
    errors = []
    for path in paths:
        filename = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            result = kb.upload_by_str(text, filename, user_id=user_id)
            entry = {"filename": filename, "result": result, "chunks": kb.last_upload_chunks}
            if result.startswith("[跳过]"):
                skipped.append(entry)
            elif result.startswith("[成功"):
                loaded.append(entry)
            else:
                errors.append(entry)
        except Exception as e:
            errors.append({"filename": filename, "error": str(e)})

    return {
        "status": "success" if not errors else "partial",
        "message": f"演示语料导入完成：新增/更新 {len(loaded)}，跳过 {len(skipped)}，失败 {len(errors)}",
        "loaded": loaded,
        "skipped": skipped,
        "errors": errors,
        "total_files": len(paths),
    }
