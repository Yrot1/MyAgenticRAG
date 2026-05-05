from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
import uvicorn
import os
import sys
import json
import hashlib

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RAG.rag import RagService
from RAG.knowledge_base import KnowledgeBaseService
from RAG.ragas_evaluator import RagasEvaluator
from RAG import config_data as config
from agent.agent_controller import AgentController
from database import get_db, init_db
from models import Conversation, KnowledgeFile, Message, User
from security import create_access_token, get_current_user, get_password_hash, verify_password

app = FastAPI(title="Agentic RAG Chat API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RagService()
kb_service = KnowledgeBaseService()
ragas_evaluator = RagasEvaluator()
agent_controller = AgentController(rag_service=rag_service)  # 与全局 RagService 共用检索

# 缓存最近一次检索的上下文（按 session_id）
context_cache = {}


@app.on_event("startup")
def on_startup():
    init_db()

class ChatRequest(BaseModel):
    message: str
    session_id: str = "user_001"
    use_agent: bool = False  # 是否使用 Agent 模式
    history: Optional[List[Dict[str, Any]]] = None  # 对话历史

class ChatResponse(BaseModel):
    response: str
    session_id: str

class UploadResponse(BaseModel):
    status: str
    message: str
    filename: str
    file_id: Optional[str] = None

class EvaluateRequest(BaseModel):
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None

class EvaluateResponse(BaseModel):
    scores: dict
    interpretation: str

class KnowledgeFileEntry(BaseModel):
    id: str
    filename: str
    chunks: int
    status: str = "success"
    last_ingested: Optional[str] = None

class KnowledgeListResponse(BaseModel):
    files: List[KnowledgeFileEntry]
    total_files: int
    total_chunks: int


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ConversationCreate(BaseModel):
    name: str = "新对话"


class ConversationUpdate(BaseModel):
    name: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None


class ConversationResponse(BaseModel):
    id: str
    name: str
    messages: List[Dict[str, Any]] = []
    createdAt: str
    updatedAt: str


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]


def serialize_user(user: User) -> UserResponse:
    return UserResponse(id=str(user.id), username=user.username, email=user.email)


def serialize_message(message: Message) -> Dict[str, Any]:
    data = {
        "role": message.role,
        "content": message.content,
        "timestamp": message.created_at.isoformat(),
    }
    if message.message_metadata:
        data["metadata"] = message.message_metadata
    if message.thinking_process:
        data["thinking_process"] = message.thinking_process
        data["showThinking"] = False
    if message.tools_called:
        data["tools_called"] = message.tools_called
    if message.feedback:
        data["feedback"] = message.feedback
    return data


def serialize_conversation(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=str(conversation.id),
        name=conversation.title,
        messages=[serialize_message(message) for message in conversation.messages],
        createdAt=conversation.created_at.isoformat(),
        updatedAt=conversation.updated_at.isoformat(),
    )


def replace_conversation_messages(
    db: Session,
    conversation: Conversation,
    user: User,
    messages: List[Dict[str, Any]],
) -> Conversation:
    conversation.messages.clear()
    db.flush()
    for item in messages:
        db.add(Message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=item.get("role", ""),
            content=item.get("content", ""),
            message_metadata=item.get("metadata") or {},
            thinking_process=item.get("thinking_process") or [],
            tools_called=item.get("tools_called") or [],
            feedback=item.get("feedback"),
        ))
    if conversation.title == "新对话":
        first_user_message = next((m for m in messages if m.get("role") == "user" and m.get("content")), None)
        if first_user_message:
            conversation.title = first_user_message["content"].strip()[:80] or "新对话"
    db.commit()
    db.refresh(conversation)
    return conversation


def get_user_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == int(conversation_id), Conversation.user_id == user.id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@app.post("/api/auth/register", response_model=TokenResponse)
async def register(payload: UserCreate, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少需要 2 个字符")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 个字符")

    exists = db.query(User).filter(or_(User.username == username, User.email == email)).first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")

    user = User(username=username, email=email, password_hash=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=serialize_user(user))


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    account = payload.username.strip()
    user = db.query(User).filter(or_(User.username == account, User.email == account.lower())).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=serialize_user(user))


@app.get("/api/auth/me", response_model=UserResponse)
async def auth_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@app.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return ConversationListResponse(conversations=[serialize_conversation(c) for c in conversations])


@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = Conversation(user_id=current_user.id, title=payload.name.strip() or "新对话")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return serialize_conversation(conversation)


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_user_conversation(db, current_user, conversation_id)
    return serialize_conversation(conversation)


@app.patch("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_user_conversation(db, current_user, conversation_id)
    if payload.name is not None:
        conversation.title = payload.name.strip() or "新对话"
    if payload.messages is not None:
        return serialize_conversation(replace_conversation_messages(db, conversation, current_user, payload.messages))
    db.commit()
    db.refresh(conversation)
    return serialize_conversation(conversation)


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_user_conversation(db, current_user, conversation_id)
    db.delete(conversation)
    db.commit()
    return {"status": "success"}

@app.post("/api/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    import traceback
    try:
        request.session_id = f"user_{current_user.id}_{request.session_id}"
        metadata_filter = {"user_id": str(current_user.id)}
        # 判断是否使用 Agent 模式
        if request.use_agent:
            # 使用 Agentic RAG 模式
            return await chat_with_agent(request, metadata_filter)
        else:
            # 使用传统 RAG 模式
            return await chat_traditional(request, metadata_filter)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"聊天错误详情：{error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

async def chat_traditional(request: ChatRequest, metadata_filter: Optional[dict] = None):
    """传统 RAG 聊天"""
    import traceback
    try:
        session_config = {
            "configurable": {
                "session_id": request.session_id
            }
        }
        
        # 先执行检索，获取当前用户的上下文
        retriever = rag_service.vector_service.get_retriever(metadata_filter=metadata_filter)
        retrieved_docs = retriever.invoke(request.message)
        contexts = [doc.page_content for doc in retrieved_docs]
        
        # 缓存检索到的上下文
        context_cache[request.session_id] = contexts
        
        # 打印调试信息
        print(f"\n=== 检索到的上下文 ===")
        print(f"问题：{request.message}")
        print(f"检索到上下文数量：{len(contexts)}")
        print(f"RAG 服务缓存的文档数量：{len(rag_service.last_retrieved_docs)}")
        for i, ctx in enumerate(contexts):
            print(f"上下文{i+1}: {ctx[:100]}...")
        print(f"====================\n")
        
        context_text = "\n\n".join([f"文档片段：{ctx}" for ctx in contexts]) or "无相关参考资料"
        history_text = "\n".join([
            f"{item.get('role', '')}: {item.get('content', '')}"
            for item in (request.history or [])[-20:]
        ]) or "无"
        messages = [
            (
                "system",
                "以提供的参考资料为主，简洁、专业地回答用户问题。"
                "如果参考资料不足，可以说明资料不足并给出通用回答。\n\n"
                f"参考资料：\n{context_text}\n\n对话历史：\n{history_text}",
            ),
            ("user", request.message),
        ]
        res_stream = rag_service.chat_model.stream(messages)
        
        async def generate():
            try:
                for chunk in res_stream:
                    content = getattr(chunk, "content", chunk)
                    if content:
                        # 发送数据块
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                # 发送上下文信息
                yield f"data: {json.dumps({'contexts': contexts}, ensure_ascii=False)}\n\n"
                # 发送结束信号
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"流式输出错误：{error_trace}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"传统聊天错误详情：{error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

async def chat_with_agent(request: ChatRequest, metadata_filter: Optional[dict] = None):
    """Agentic RAG 聊天"""
    import traceback
    try:
        # 使用 Agent 控制器执行，传入 session_id 和 history
        result = agent_controller.execute(
            question=request.message,
            session_id=request.session_id,
            history=request.history,
            metadata_filter=metadata_filter,
        )
        
        # 流式输出答案
        async def generate():
            try:
                # 发送答案
                answer = result["answer"]
                for i in range(0, len(answer), 10):
                    chunk = answer[i:i+10]
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                
                # 发送完整元数据（包含思考过程和工具调用）
                yield f"data: {json.dumps({
                    'contexts': result['contexts'],
                    'thinking_process': result['thinking_process'],
                    'tools_called': result['tools_called'],
                    'metadata': result['metadata'],
                    'evaluation': result['evaluation'],
                    'conversation_history': result.get('conversation_history', [])
                }, ensure_ascii=False)}\n\n"
                
                # 发送结束信号
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"Agent 流式输出错误：{error_trace}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Agent 聊天错误详情：{error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import traceback
    try:
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "text/markdown",
            "text/plain"
        ]
        
        if file.content_type not in allowed_types and not file.filename.endswith(('.pdf', '.docx', '.doc', '.csv', '.xlsx', '.xls', '.md', '.txt')):
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        content = await file.read()
        
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = content.decode('gbk')
            except:
                text = content.decode('utf-8', errors='ignore')
        
        file_hash = hashlib.md5(content).hexdigest()
        existing = (
            db.query(KnowledgeFile)
            .filter(KnowledgeFile.user_id == current_user.id, KnowledgeFile.file_hash == file_hash)
            .first()
        )
        file_row = existing
        if not file_row:
            file_row = KnowledgeFile(
                user_id=current_user.id,
                filename=file.filename,
                file_hash=file_hash,
                chunks=0,
                status="processing",
            )
            db.add(file_row)
        else:
            file_row.filename = file.filename
            file_row.status = "processing"
        db.commit()
        db.refresh(file_row)

        try:
            result = kb_service.upload_by_str(text, file.filename, user_id=current_user.id)
            file_row.chunks = kb_service.last_upload_chunks or file_row.chunks
            file_row.status = "success"
            file_row.last_ingested = datetime.utcnow()
            db.commit()
            db.refresh(file_row)
        except Exception:
            file_row.status = "failed"
            db.commit()
            raise
        
        return UploadResponse(
            status="success",
            message=result,
            filename=file.filename,
            file_id=str(file_row.id),
        )
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"上传错误详情：{error_trace}")
        raise HTTPException(status_code=500, detail=f"上传失败：{str(e)}")

async def _kb_list_files_impl(current_user: User, db: Session) -> KnowledgeListResponse:
    """列出当前用户知识库文件（以 PostgreSQL 记录为准）"""
    try:
        rows = (
            db.query(KnowledgeFile)
            .filter(KnowledgeFile.user_id == current_user.id)
            .order_by(KnowledgeFile.updated_at.desc())
            .all()
        )
        return KnowledgeListResponse(
            files=[
                KnowledgeFileEntry(
                    id=str(row.id),
                    filename=row.filename,
                    chunks=row.chunks,
                    status=row.status,
                    last_ingested=row.last_ingested.isoformat() if row.last_ingested else None,
                )
                for row in rows
            ],
            total_files=len(rows),
            total_chunks=sum(row.chunks for row in rows),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取知识库列表失败：{str(e)}")


@app.get("/api/files", response_model=KnowledgeListResponse)
async def list_kb_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识库文件列表（推荐路径）"""
    return await _kb_list_files_impl(current_user, db)


@app.get("/api/knowledge/files", response_model=KnowledgeListResponse)
async def list_kb_files_nested(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识库文件列表（兼容路径）"""
    return await _kb_list_files_impl(current_user, db)


@app.delete("/api/files/{file_id}")
async def delete_kb_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(KnowledgeFile)
        .filter(KnowledgeFile.id == file_id, KnowledgeFile.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    deleted_vectors = kb_service.delete_by_source(row.filename, user_id=current_user.id)
    db.delete(row)
    db.commit()
    return {"status": "success", "deleted_vectors": deleted_vectors}

@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate_answer(request: EvaluateRequest, current_user: User = Depends(get_current_user)):
    """
    评估 RAG 回答质量（使用 RAGAS）
    """
    import traceback
    try:
        # 打印调试信息
        print(f"\n=== 评估请求 ===")
        print(f"问题：{request.question}")
        print(f"答案：{request.answer[:100]}...")
        print(f"原始上下文数量：{len(request.contexts)}")
        
        # 过滤掉不相关的上下文（简单方法：检查是否包含问题关键词）
        def is_context_relevant(context: str, question: str) -> bool:
            # 提取问题中的关键词（去除停用词）
            stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', 
                         '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', 
                         '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '什么'}
            keywords = [w for w in question if w not in stop_words and len(w) > 0]
            
            # 检查上下文是否包含至少一个关键词
            for keyword in keywords:
                if keyword in context:
                    return True
            return False
        
        # 过滤相关上下文
        relevant_contexts = [ctx for ctx in request.contexts if is_context_relevant(ctx, request.question)]
        
        print(f"过滤后相关上下文数量：{len(relevant_contexts)}")
        for i, ctx in enumerate(relevant_contexts):
            print(f"相关上下文{i+1}: {ctx[:100]}...")
        print(f"================\n")
        
        # 如果没有相关上下文，使用所有上下文
        if not relevant_contexts:
            relevant_contexts = request.contexts
        
        # 执行评估
        scores = ragas_evaluator.evaluate_single(
            question=request.question,
            answer=request.answer,
            contexts=relevant_contexts,
            ground_truth=request.ground_truth
        )
        
        # 获取解释
        interpretation = ragas_evaluator.get_evaluation_interpretation(scores)
        
        # 添加评估说明
        interpretation += "\n\n📌 评估说明：\n"
        interpretation += "- 忠实度：衡量答案是否基于检索内容（客观指标）\n"
        interpretation += "- 相关性：通过反向生成问题评估（可能受中文表达影响）\n"
        interpretation += "- 建议重点关注忠实度分数，相关性仅供参考"
        
        print(f"评估结果：{scores}")
        
        return EvaluateResponse(
            scores=scores,
            interpretation=interpretation
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"评估错误详情：{error_trace}")
        raise HTTPException(status_code=500, detail=f"评估失败：{str(e)}")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "model": config.chat_model_name,
        "embedding_model": config.embedding_model_name,
        "api_key_configured": bool(config.llm_api_key),
        "database_configured": bool(config.database_url),
        "cors_allow_origins": config.cors_allow_origins,
    }

if __name__ == "__main__":
    uvicorn.run(app, host=config.backend_host, port=config.backend_port)
