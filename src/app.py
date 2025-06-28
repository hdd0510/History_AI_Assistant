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
from src.graph_structure.graph import tools_list, custom_prompt

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

    # Thêm biến đếm lượt hỏi đáp cho mỗi user
    app.state.user_pool[user_id] = {"turn_count": {}}

    saver_ctx = MongoDBSaver.from_conn_string(MONGO_URI, user_id)
    saver     = saver_ctx.__enter__()
    agent     = create_react_agent(
        model="google_genai:gemini-2.0-flash",
        tools=tools_list,
        prompt=custom_prompt,
        checkpointer=saver
    )
    digger = CheckpointDigger(saver.db)
    user_profile = saver.db["user_profile"]

    app.state.user_pool[user_id].update({
        "saver_ctx":    saver_ctx,
        "saver":        saver,
        "agent":        agent,
        "digger":       digger,
        "user_profile": user_profile,
    })
    return app.state.user_pool[user_id]

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    res   = await _get_resources(req.user_id, app)
    agent = res["agent"]
    user_profile  = res["user_profile"]
    print(user_profile)
    if not agent:
        raise HTTPException(503, "Agent chưa sẵn sàng!")
    
    profile_doc = user_profile.find_one({"user_id": req.user_id}) or {}
    profile_description = profile_doc.get("profile_description", "unknown")

    prefix = (
        f"User Profile ➡️ {profile_description}\n"
    )
    print(f"Prefuix: {prefix}")

    full_messages = [
        {"role": "system", "content": prefix},
        {"role": "user",   "content": req.message},
    ]
    resp = agent.invoke(
        {"messages": full_messages},
        {"configurable": {"thread_id": req.thread_id}},
    )
    bot_reply = resp["messages"][-1].content

    # Đếm số lượt hỏi đáp và chỉ cập nhật profile mỗi 5 lượt
    user_turns = res.setdefault("turn_count", {})
    thread_key = req.thread_id
    user_turns[thread_key] = user_turns.get(thread_key, 0) + 1
    print(f"Turn count for user {req.user_id}, thread {thread_key}: {user_turns[thread_key]}")
    if user_turns[thread_key] % 5 == 0:
        # Lấy 5 QA pair gần nhất từ lịch sử chat
        digger = res["digger"]
        contents = digger(thread_key)
        # Mỗi QA là 2 turn: user, assistant. Lấy 10 message cuối cùng
        last_10 = contents[-10:] if contents else []
        # Gom thành 5 cặp (user, assistant)
        qa_pairs = []
        for i in range(0, len(last_10), 2):
            if i+1 < len(last_10):
                qa_pairs.append((last_10[i], last_10[i+1]))
        # Nếu chưa đủ 5 cặp thì lấy hết
        qa_pairs = qa_pairs[-5:]
        # Tạo đoạn hội thoại tổng hợp
        history_str = "\n".join([
            f"User: {q}\nAssistant: {a}" for q, a in qa_pairs
        ])
        await extract_info(req.user_id,
                           history_str,  # truyền toàn bộ 5 QA pair vào user_msg
                           user_profile)  # user_profile là MongoDB collection
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

async def extract_info(user_id: str,
                      history_str: str,
                      user_profile_collection):    # truyền collection vào đây
    # Lấy profile cũ từ collection
    old_profile = user_profile_collection.find_one({"user_id": user_id}) or {}
    print("--------------------")
    print("Old profile:", old_profile)
    prompt = f"""
        Bạn là công cụ cập nhật hồ sơ người dùng. Dưới đây là thông tin hồ sơ hiện tại của user, và một đoạn hội thoại mới giữa user và assistant:
        ---
        Hồ sơ hiện tại: {old_profile}
        Hội thoại: {history_str}
        ---
        Hãy cập nhật hồ sơ người dùng theo thông tin mới. Trong user profile phải có ít nhất các trường: tên, người dùng là ai?, chủ đề người dùng đang quan tâm, mục tiêu học tập.
        Chỉ giữ nhưng thông tin về giao tiếp và học thuật về người dùng, những thông tin ngoài lề như ngày tháng năm, thời gian, ... thì không cần cập nhật.
        Output sẽ là 1 profile được cập nhật ví dụ như:
        "Người dùng tên là Dũng, người dùng là sinh viên, chủ đề người dùng đang quan tâm là lập trình, mục tiêu học tập là trở thành lập trình viên, yêu thích về lịch sử, đang quan tâm về lịch sử năm 1845, mục tiêu ..."
        """.strip()

    model = init_chat_model(
        "google_genai:gemini-2.0-flash",
        temperature=0
    )
    raw = model.invoke(prompt).content.strip()
    print("RAW EXTRACT:", raw)

    # Cố gắng lấy đoạn mô tả profile trả về từ LLM (string)
    profile_description = raw.strip()

    # Cập nhật vào MongoDB collection
    user_profile_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "profile_description": profile_description,
        }},
        upsert=True
    )
    print(f"Đã upsert profile cho user_id={user_id}: profile_description={profile_description}")