from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import sys
import re
from langchain.chat_models import init_chat_model
sys.path.append("/home/vanh/chatbot_fpt/vanh_draft")
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.mongodb import MongoDBSaver
from digger import CheckpointDigger
import os

# Gán trực tiếp API key tại đây – thay bằng key của bạn
GOOGLE_API_KEY = "AIzaSyDXa2DMUauAzfbZjBfYLwaiG5zZ56D8fP4"

# Đặt biến môi trường
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ==== Config ====
MONGO_URI = "mongodb://localhost:27017"
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
    # close every saver_ctx
    for res in app.state.user_pool.values():
        res["saver_ctx"].__exit__(None, None, None)

# ==== Tạo app với lifespan ====
app = FastAPI(lifespan=lifespan, title="Chat Agent API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],        # GET, POST, PUT, DELETE...
    allow_headers=["*"],        # Authorization, Content-Type...
)

async def _get_resources(user_id: str, app: FastAPI):
    if user_id in app.state.user_pool:
        return app.state.user_pool[user_id]

    saver_ctx = MongoDBSaver.from_conn_string(MONGO_URI, user_id)
    saver     = saver_ctx.__enter__()
    agent     = create_react_agent(
        model="google_genai:gemini-2.0-flash",
        tools=[],
        checkpointer=saver
    )
    digger = CheckpointDigger(saver.db)
    user_profile = saver.db["user_profile"]

    app.state.user_pool[user_id] = {
        "saver_ctx":    saver_ctx,
        "saver":        saver,
        "agent":        agent,
        "digger":       digger,
        "user_profile": user_profile,
    }
    return app.state.user_pool[user_id]

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    res   = await _get_resources(req.user_id, app)
    agent = res["agent"]
    user_profile  = res["user_profile"]
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
    resp = agent.invoke(
        # {"messages": [{"role": "user", "content": full_messages}]},
        {"messages": full_messages},
        {"configurable": {"thread_id": req.thread_id}},
    )
    bot_reply = resp["messages"][-1].content

    await extract_info(req.user_id,
                       req.message, bot_reply,
                       user_profile)
    return ChatResponse(reply=bot_reply)

@app.get("/chat-history/{user_id}/{thread_id}", response_model=List[ChatMessage])
async def get_chat_history(user_id: str, thread_id: str):
    res     = await _get_resources(user_id, app)
    digger  = res["digger"]
    contents = digger(thread_id)

    if not contents:
        raise HTTPException(404, "Không tìm thấy lịch sử chat.")
    
    history: List[ChatMessage] = []
    for i, txt in enumerate(contents):
        # ép kiểu, nếu list/dict thì lấy str(txt)
        text = txt if isinstance(txt, str) else str(txt)
        history.append(ChatMessage(
            role="user" if i % 2 == 0 else "assistant",
            contents=text
        ))
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