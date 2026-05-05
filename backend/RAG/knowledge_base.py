"""
知识库
"""
import os
import sys

# 添加当前目录到路径，确保可以导入同目录的 config_data
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import config_data as config
import hashlib
from langchain_chroma import Chroma
from langchain_community.embeddings import ZhipuAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from datetime import datetime
from collections import defaultdict

def check_md5(md5_str:str):
    "检查传入的md5字符串是否已经被处理过了"
    if not os.path.exists(config.md5_path):
        # if进入表示文件不存在，说明没有处理过这个md5
        open(config.md5_path,"w",encoding="utf-8").close()
        return False
    else:
        for line in open(config.md5_path,'r',encoding="utf-8").readlines():
            line = line.strip() # 处理字符串前后的空格和回车
            if line==md5_str:
                return True # 已处理过
        return False


def save_md5(md5_str:str):
    "将传入的md5字符串，记录到文件内保存"
    with open(config.md5_path,'a',encoding="utf-8") as f:
        f.write(md5_str + '\n')


def get_string_md5(input_str: str, encoding: str = "utf-8") -> str:
    "将传入的字符串转换为md5字符串"
    md5_obj = hashlib.md5()
    md5_obj.update(input_str.encode(encoding=encoding))
    return md5_obj.hexdigest()

def _is_markdown_file(filename: str) -> bool:
    if not filename:
        return False
    lower = filename.lower()
    return lower.endswith(".md") or lower.endswith(".markdown")


def _flatten_header_metadata(meta: dict) -> dict:
    """Chroma metadata 仅支持扁平标量，去掉空值"""
    out = {}
    for k, v in (meta or {}).items():
        if v is None or v == "":
            continue
        out[str(k)] = str(v)
    return out


class KnowledgeBaseService(object):
    def __init__(self):
        # 如果文件夹不存在则创建，如果存在则跳过
        os.makedirs(config.persist_directory,exist_ok=True)
        self.chroma=Chroma(
            collection_name=config.collection_name,
            embedding_function=ZhipuAIEmbeddings(
                model=config.embedding_model_name,
                api_key=config.llm_api_key
            ),
            persist_directory=config.persist_directory,
        ) # 向量存储的实例 Chroma 数据库
        self.spliter=RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,  # 分割后的文本段的最大长度
            chunk_overlap=config.chunk_overlap, # 连续文本段之间的字符重叠数量
            separators=config.separators,  # 自然段落划分的符号
            length_function=len, # 使用 python 自带的 len 函数做长度统计的依据
        ) # 文本分割器的对象
        self._md_headers = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self._md_headers,
            strip_headers=False,
        )
        self.last_upload_chunks = 0

    def _refine_oversized_sections(self, sections: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
        """标题块超过 chunk_size 时，用 RecursiveCharacterTextSplitter 二次切分，保留标题 metadata"""
        refined: list[tuple[str, dict]] = []
        for text, meta in sections:
            text = (text or "").strip()
            if not text:
                continue
            if len(text) <= config.chunk_size:
                refined.append((text, meta.copy()))
                continue
            for sub in self.spliter.split_text(text):
                sub = sub.strip()
                if sub:
                    refined.append((sub, meta.copy()))
        return refined

    def _split_markdown(self, data: str) -> list[tuple[str, dict]]:
        """按 Markdown 标题切块，再对超长节做字数切分"""
        docs = self.markdown_splitter.split_text(data)
        if not docs:
            if len(data) <= config.max_split_char_number:
                return [(data.strip(), {})]
            return [(t.strip(), {}) for t in self.spliter.split_text(data) if t.strip()]

        pairs: list[tuple[str, dict]] = []
        for doc in docs:
            content = (doc.page_content or "").strip()
            if not content:
                continue
            meta = _flatten_header_metadata(doc.metadata or {})
            pairs.append((content, meta))

        return self._refine_oversized_sections(pairs)

    def upload_by_str(self, data, filename, user_id: int | None = None):
        "将传入的字符串，进行向量话，存入向量数据库中"
        self.last_upload_chunks = 0
        # 先得到传入字符串的 md5 值
        md5_hex = get_string_md5(data)
        md5_key = f"user:{user_id}:{md5_hex}" if user_id is not None else md5_hex
        if check_md5(md5_key):
            return "[跳过] 内容已经存在知识库中"
        
        # 打印文件信息用于调试
        print(f"上传文件：{filename}, 内容长度：{len(data)} 字符")
        
        # 文本分割：Markdown 按标题；其它格式沿用 RecursiveCharacterTextSplitter
        if _is_markdown_file(filename):
            knowledge_chunks = self._split_markdown(data)
        elif len(data) > config.max_split_char_number:
            knowledge_chunks = [(t.strip(), {}) for t in self.spliter.split_text(data) if t.strip()]
        else:
            knowledge_chunks = [(data.strip(), {})]

        knowledge_chunks = [(t, m) for t, m in knowledge_chunks if t and t.strip()]
        
        print(f"分割后文本段数量：{len(knowledge_chunks)}")
        if knowledge_chunks:
            print(f"第一个文本段预览：{knowledge_chunks[0][0][:200]}...")
        
        if not knowledge_chunks:
            return "[错误] 文件内容为空或无法分割"
        
        # 逐个处理文本段，避免批量处理时的 API 参数问题
        success_count = 0
        failed_chunks = []
        for i, (chunk, header_meta) in enumerate(knowledge_chunks):
            try:
                metadata = {
                    "source": filename,
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator": "小帅",
                }
                if user_id is not None:
                    metadata["user_id"] = str(user_id)
                metadata.update(header_meta)
                
                self.chroma.add_texts(
                    [chunk],
                    metadatas=[metadata],
                )
                success_count += 1
                print(f"成功处理第 {i+1}/{len(knowledge_chunks)} 个文本段")
            except Exception as e:
                failed_chunks.append(i)
                print(f"第 {i+1} 个文本段处理失败：{str(e)[:100]}")
                print(f"失败文本段预览：{chunk[:200]}...")
        
        if failed_chunks:
            print(f"共有 {len(failed_chunks)} 个文本段处理失败")
        
        print(f"成功处理 {success_count}/{len(knowledge_chunks)} 个文本段")
        
        self.last_upload_chunks = success_count
        save_md5(md5_key)
        return "[成功！] 内容已经成功载入向量库"

    def list_sources(self, user_id: int | None = None):
        """列出向量库中已入库的文件（按 metadata.source 聚合切片数）"""
        try:
            batch = self.chroma.get(include=["metadatas"])
        except Exception as e:
            print(f"list_sources 查询失败：{e}")
            return {"files": [], "total_files": 0, "total_chunks": 0}
        metadatas = batch.get("metadatas") or []
        agg = defaultdict(lambda: {"chunks": 0, "last_time": ""})
        for m in metadatas:
            if not m:
                continue
            if user_id is not None and str(m.get("user_id") or "") != str(user_id):
                continue
            src = (m.get("source") or "未知来源").strip() or "未知来源"
            agg[src]["chunks"] += 1
            t = str(m.get("create_time") or "")
            if t >= agg[src]["last_time"]:
                agg[src]["last_time"] = t
        files = []
        for fn in sorted(agg.keys(), key=lambda x: x.lower()):
            info = agg[fn]
            files.append({
                "filename": fn,
                "chunks": info["chunks"],
                "last_ingested": info["last_time"] or None,
            })
        total_chunks = sum(f["chunks"] for f in files)
        return {
            "files": files,
            "total_files": len(files),
            "total_chunks": total_chunks,
        }

    def delete_by_source(self, filename: str, user_id: int | None = None) -> int:
        """删除指定用户指定文件对应的 Chroma 向量，返回删除数量"""
        try:
            batch = self.chroma.get(include=["metadatas"])
        except Exception as e:
            print(f"delete_by_source 查询失败：{e}")
            return 0

        ids = batch.get("ids") or []
        metadatas = batch.get("metadatas") or []
        delete_ids = []
        for doc_id, metadata in zip(ids, metadatas):
            if not metadata:
                continue
            same_source = (metadata.get("source") or "") == filename
            same_user = user_id is None or str(metadata.get("user_id") or "") == str(user_id)
            if same_source and same_user:
                delete_ids.append(doc_id)

        if delete_ids:
            self.chroma.delete(ids=delete_ids)
        return len(delete_ids)


if __name__ == '__main__':
    service = KnowledgeBaseService()
    r=service.upload_by_str("周杰伦","testfile")
    print(r)















