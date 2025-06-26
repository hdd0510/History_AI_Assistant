import os
from langchain.chat_models import init_chat_model
from langchain.schema import HumanMessage
from langchain.chains import ConversationChain

# 1. Thiết lập API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDXa2DMUauAzfbZjBfYLwaiG5zZ56D8fP4"

# 2. Khởi tạo chat model
model = init_chat_model(
    "google_genai:gemini-2.0-flash",
    temperature=0,
    # other parameters
)

respond = model.invoke("Tôi tên là gì?").content
print(respond)