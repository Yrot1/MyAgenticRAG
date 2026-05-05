import os,json
from typing import Sequence
from langchain_core.messages import message_to_dict,messages_from_dict,BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory

# 获取当前文件所在目录（RAG 目录）
RAG_DIR = os.path.dirname(os.path.abspath(__file__))

def get_history(config):
    # 处理 config 可能是字符串或字典的情况
    if isinstance(config, str):
        session_id = config
    elif isinstance(config, dict):
        session_id = config.get("configurable", {}).get("session_id", "user_001")
    else:
        session_id = "user_001"
    # 聊天历史存储在 RAG/chat_history 目录
    return FileChatMessageHistory(session_id, os.path.join(RAG_DIR, "chat_history"))


class FileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self,session_id,storage_path):
        self.session_id = session_id
        self.storage_path = storage_path
        #完整的文件路径
        self.file_path = os.path.join(self.storage_path,self.session_id)
        # 确定文件夹是否存在
        os.makedirs(os.path.dirname(self.file_path),exist_ok=True)

    def add_messages(self,messages:Sequence[BaseMessage]) -> None:
        # Sequence序列  类似list,tuple
        all_messages=list(self.messages)
        all_messages.extend(messages)

        new_messages=[message_to_dict(messages) for messages in all_messages]
        # 将数据写入文件
        with open(self.file_path,"w",encoding="utf-8") as f:
            json.dump(new_messages, f)

    @property
    def messages(self) -> list[BaseMessage]:
        # 当前文件内：list[字典]
        try:
            with open(self.file_path,"r",encoding="utf-8") as f:
                messages_data = json.load(f)
                return messages_from_dict(messages_data)
        except FileNotFoundError:
            return []

    def clear(self) -> None:
        with open(self.file_path,"w",encoding="utf-8") as f:
            json.dump([], f)