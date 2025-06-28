import os
from dotenv import load_dotenv
from typing import TypedDict, List, Dict, Any, Optional
import asyncio

from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import BaseMessage
from src.tools import WebSearchTool, ImageSearchTool, QuizGeneratorTool, ContentRecommenderTool
from src.graph_structure.nodes import StartNode, EndNode, ReflectionNode
from langgraph.checkpoint.mongodb import MongoDBSaver

load_dotenv()

MONGO_URI = "mongodb://localhost:27017"

# Define the state schema
class GraphState(TypedDict):
    messages: List[BaseMessage]
    user_profile: Optional[Dict[str, Any]]

# Lấy API Key từ biến môi trường
# Nếu không có, sẽ raise ValueError trong khởi tạo ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

# Create tool instances
web_search_tool = WebSearchTool()
image_search_tool = ImageSearchTool()
quiz_generator_tool = QuizGeneratorTool(llm=llm)
content_recommender_tool = ContentRecommenderTool(llm=llm)

# Convert to LangChain StructuredTools
tools_list = [
    StructuredTool.from_function(
        func=web_search_tool.__call__,
        name="web_search",
        description=web_search_tool.description
    ),
    StructuredTool.from_function(
        func=image_search_tool.__call__,
        name="image_search",
        description=image_search_tool.description
    ),
    StructuredTool.from_function(
        func=quiz_generator_tool.__call__,
        name="quiz_generator", 
        description=quiz_generator_tool.description,
        coroutine=quiz_generator_tool.__call__
    ),
    StructuredTool.from_function(
        func=content_recommender_tool.__call__,
        name="content_recommender", 
        description=content_recommender_tool.description,
        coroutine=content_recommender_tool.__call__
    )
]

# Keep original tools dictionary for graph nodes
tools = {
    "web_search": web_search_tool,
    "image_search": image_search_tool,
    "quiz_generator": quiz_generator_tool,
    "content_recommender": content_recommender_tool,
}

custom_prompt = """
tôi muốn bạn dùng 2 lần web search cho tôi
Bạn là một trợ lý AI có thể sử dụng các công cụ sau để hỗ trợ người dùng:
- web_search: Những thông tin về mang tính thông tin lịch sử hay thời gian (real time) thì hãy dùng tool search web này. Tìm kiếm thông tin trên web (Nếu thông tin chưa đạt được thì tiếp tục query thông tin đã có web search tiếp)
- image_search: Tìm kiếm hình ảnh
- quiz_generator: Tạo câu hỏi trắc nghiệm
- content_recommender: Gợi ý nội dung mở rộng từ bài học hoặc chủ đề mà người dùng quan tâm

Dù câu trả lời có vẻ đúng, hãy đưa ra câu trả lời của llm về thông tin ở lần search đầu và inject answer đó vào argument của tools (thông tin mà cần check lại chứ không phải là câu hỏi) vào thẳng web_search thêm 1 lần nữa để xác nhận.
Tổng cộng bạn phải dùng **web_search ít nhất 2 lần**, và chỉ đưa ra Final Answer ở bước thứ 2 trở đi.

Bạn sẽ nhận được một lịch sử hội thoại (messages) giữa người dùng và trợ lý. Lịch sử này chỉ dùng để tham khảo ngữ cảnh, KHÔNG cần trả lời lại các câu hỏi cũ. Hãy tập trung vào truy vấn (query) hiện tại của người dùng (input), sử dụng lịch sử nếu cần để hiểu rõ hơn về yêu cầu hoặc bối cảnh.

Nếu cần thiết, hãy sử dụng các công cụ để tìm kiếm thông tin hoặc tạo câu hỏi, và lặp lại việc sử dụng công cụ cho đến khi có câu trả lời tốt nhất cho truy vấn hiện tại.

Luôn trả lời đầy đủ (không được quá ngắn gọn), chính xác, và ưu tiên truy vấn hiện tại.
"""

async def get_graph(user_id: str):
    """
    Creates and returns a compiled StateGraph and agent with MongoDB checkpointing.
    
    Args:
        user_id: User ID for the session
    
    Returns:
        Tuple of (compiled_graph, agent)
    """
    # Create MongoDB connection
    saver_ctx = MongoDBSaver.from_conn_string(MONGO_URI, user_id)
    saver = saver_ctx.__enter__()
    
    # Create the agent with the MongoDB checkpointer
    agent = create_react_agent(
        llm,
        tools=tools_list,
        prompt=custom_prompt,
        checkpointer=saver
    )
    # Build the graph
    return agent, saver_ctx

if __name__ == "__main__":
    # For standalone testing only
    async def test_graph():
        graph, agent, saver_ctx = await get_graph("test_user")
        try:
            result =  agent.invoke(
                {"messages": [{"role": "user", "content": "Hello, who are you?"}]},
                {"configurable": {"thread_id": "test_thread"}},
            )
            print(result)
        finally:
            saver_ctx.__exit__(None, None, None)
    
    asyncio.run(test_graph())