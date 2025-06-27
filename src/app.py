from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, TypedDict, Annotated
import sys
import re
from langchain.chat_models import init_chat_model
sys.path.append("/app/vanh_draft")
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph.message import add_messages
from digger import CheckpointDigger
import os
import pymongo
from src.graph_structure.graph import tools_list, custom_prompt
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from datetime import datetime
import logging

# Gán trực tiếp API key tại đây – thay bằng key của bạn
GOOGLE_API_KEY = "AIzaSyDXa2DMUauAzfbZjBfYLwaiG5zZ56D8fP4"

# Đặt biến môi trường
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ==== Config ====
MONGO_URI = "mongodb://admin:password123@mongodb:27017/history_ai?authSource=admin"
user_pool: Dict[str, Dict] = {}

class ChatMessage(BaseModel):
    role: str
    contents: str

class ChatRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str

class UserProfile(BaseModel):
    user_id: str
    name: str
    style: str
    learning_goal: str

def get_weather(city: str) -> str:
    """
    Trả về chuỗi mô tả thời tiết cho thành phố đã cho.
    Ví dụ: "It's always sunny in Hanoi!"
    """
    return f"It's always sunny in {city}!"

# ==== Lifespan handler to enter & exit context manager ====
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.user_pool = {}
    yield
    # Cleanup user pool
    app.state.user_pool.clear()

# ==== Tạo app với lifespan ====
app = FastAPI(
    lifespan=lifespan, 
    title="Chat Agent API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],      # Expose tất cả headers
)

# Thêm endpoint OPTIONS để xử lý preflight requests
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {"message": "OK"}

# Thêm endpoint test để kiểm tra CORS
@app.get("/test-cors")
async def test_cors():
    return {"message": "CORS is working!", "timestamp": datetime.now()}

# Thêm endpoint health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }

# Thêm endpoint root
@app.get("/")
async def root():
    return {
        "message": "History AI Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

async def _get_resources(user_id: str, app: FastAPI):
    if user_id in app.state.user_pool:
        return app.state.user_pool[user_id]

    saver = MemorySaver()
    
    # Tạo agent với StateGraph trực tiếp
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
    
    # Define state
    class AgentState(TypedDict):
        messages: Annotated[list[BaseMessage], add_messages]
    
    # Create workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", lambda state: {"messages": [llm.invoke(state["messages"])]})
    
    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    
    # Compile
    agent = workflow.compile(checkpointer=saver)
    
    # Tạo MongoDB connection riêng cho digger và user_profile
    client = pymongo.MongoClient(MONGO_URI)
    db_name = MONGO_URI.split("/")[-1].split("?")[0]
    db = client[db_name]
    digger = CheckpointDigger(db)
    user_profile = db["user_profile"]

    app.state.user_pool[user_id] = {
        "saver":        saver,
        "agent":        agent,
        "digger":       digger,
        "user_profile": user_profile,
        "db":           db,
    }
    return app.state.user_pool[user_id]

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    res   = await _get_resources(req.user_id, app)
    agent = res["agent"]
    user_profile  = res["user_profile"]
    db = res["db"]
    if not agent:
        raise HTTPException(503, "Agent chưa sẵn sàng!")
    
    profile_doc = user_profile.find_one({"user_id": req.user_id}) or {}
    name        = profile_doc.get("name", "unknown")
    style       = profile_doc.get("style", "unknown")
    topics      = profile_doc.get("learning_goal", [])
    topics_str  = ", ".join(topics) if topics else "unknown"

    prefix = (
        f"User Profile ➡️ Name: {name}; "
        f"ChatStyle: {style}; "
        f"Topics: {topics_str}.\n"
        "// Đừng hỏi thêm, chỉ dùng cái profile này để tùy biến reply.\n"
    )
    print(f"Prefuix: {prefix}")

    full_messages = [
        {"role": "system", "content": prefix},
        {"role": "user",   "content": req.message},
    ]
    
    messages = [
        SystemMessage(content=prefix),
        HumanMessage(content=req.message)
    ]
    
    resp = agent.invoke(
        {"messages": messages},
        {"configurable": {"thread_id": req.thread_id}},
    )
    
    # Lấy reply từ response
    if "messages" in resp and resp["messages"]:
        bot_reply = resp["messages"][-1].content
    else:
        bot_reply = "Xin lỗi, tôi không thể xử lý yêu cầu của bạn."

    # Lưu chat history vào MongoDB
    chat_history_collection = db["chat_history"]
    chat_history_collection.insert_one({
        "user_id": req.user_id,
        "thread_id": req.thread_id,
        "timestamp": datetime.now(),
        "user_message": req.message,
        "bot_reply": bot_reply,
        "role": "user"
    })
    chat_history_collection.insert_one({
        "user_id": req.user_id,
        "thread_id": req.thread_id,
        "timestamp": datetime.now(),
        "user_message": req.message,
        "bot_reply": bot_reply,
        "role": "assistant"
    })

    await extract_info(req.user_id,
                       req.message, bot_reply,
                       user_profile)
    return ChatResponse(reply=bot_reply)

@app.get("/chat-history/{user_id}/{thread_id}", response_model=List[ChatMessage])
async def get_chat_history(user_id: str, thread_id: str):
    res = await _get_resources(user_id, app)
    db = res["db"]
    
    # Đọc chat history từ collection chat_history
    chat_history_collection = db["chat_history"]
    cursor = chat_history_collection.find({
        "user_id": user_id,
        "thread_id": thread_id
    }).sort("timestamp", 1)  # Sắp xếp theo thời gian
    
    history: List[ChatMessage] = []
    for doc in cursor:
        if doc["role"] == "user":
            history.append(ChatMessage(
                role="user",
                contents=doc["user_message"]
            ))
        elif doc["role"] == "assistant":
            history.append(ChatMessage(
                role="assistant", 
                contents=doc["bot_reply"]
            ))
    
    if not history:
        raise HTTPException(404, "Không tìm thấy lịch sử chat.")
    
    return history

async def extract_info( user_id: str,
                       user_msg: str, bot_msg: str,
                       user_profile):    # truyền collection vào đây
    old = user_profile.find_one({"user_id": user_id}) or {}
    old_topics = set(old.get("learning_goal", []))
    old_name   = old.get("name", "")
    old_style  = old.get("style", "")
    print(user_msg)
    print(bot_msg)
    print("--------------------")
    prompt = f"""
        Bạn là công cụ phân tích đoạn chat. Từ đoạn hội thoại sau giữa người dùng và trợ lý:
        ---
        User: {user_msg}
        Assistant: {bot_msg}
        ---
        Hãy trả về **chính xác một dòng** theo định dạng:
        Name: <tên người dùng hoặc 'unknown'>, ChatStyle: <phong cách chat hoặc 'unknown'>, Topics: <danh sách chủ đề hoặc 'unknown'>.
        Nếu không tìm thấy, ghi 'unknown'.
        
        **Chỉ** output đúng 1 dòng, không dấu ngoặc kép, không xuống dòng, không giải thích.
        """.strip()


    model = init_chat_model(
        "google_genai:gemini-2.0-flash",
        temperature=0
    )
    
    raw = model.invoke(prompt).content.strip()

    print("RAW EXTRACT:", raw)
    m = re.match(
        r"Name:\s*(.*?),\s*ChatStyle:\s*(.*?),\s*Topics:\s*(.*)$",
        raw
    )
    print(f"extract_info: {m}")

    if not m:
        print("Không khớp định dạng:", raw)
        return

    name, style, topics_str = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    new_topics = {t.strip() for t in topics_str.split(",")
                  if t.strip().lower() != "unknown"}
    topics_to_add = new_topics - old_topics
    if name == old_name and style == old_style and not topics_to_add:
        print("Không có thay đổi, skip upsert")
        return

    merged_topics = old_topics.union(new_topics)
    user_profile.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id":       user_id,
            "name":          name if name.lower() != "unknown" else old_name,
            "style":         style if style.lower() != "unknown" else old_style,
            "learning_goal": list(merged_topics),
        }},
        upsert=True
    )
    print(f"Đã upsert: name={name}, style={style}, thêm topics={topics_to_add}")