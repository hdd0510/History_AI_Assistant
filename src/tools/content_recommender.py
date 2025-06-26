from typing import Dict, List, Optional
import os
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

class ContentRecommenderTool:
    name = "content_recommender"
    description = (
        "Gợi ý nội dung mở rộng từ bài học hoặc chủ đề mà người dùng quan tâm. "
        "Tool này giúp đề xuất các tài liệu, khóa học, chủ đề liên quan để người dùng có thể học sâu hơn."
    )

    def __init__(self, llm):
        self.llm = llm
        # Define the prompt for generating content recommendations
        self.recommendation_prompt = PromptTemplate.from_template(
            """Bạn là một chuyên gia giáo dục có kinh nghiệm đề xuất tài liệu học tập.
            Dựa trên chủ đề/bài học: {topic} và các thông tin trong {context}, 
            hãy đề xuất {num_recommendations} nội dung mở rộng để người dùng có thể học sâu hơn.
            
            Mỗi đề xuất phải bao gồm:
            1. Tiêu đề nội dung đề xuất
            2. Mô tả ngắn gọn về nội dung và lý do đề xuất
            3. Loại tài liệu (sách, khóa học online, video, bài viết, podcast, ...)
            4. Mức độ phù hợp (cơ bản, trung bình, nâng cao)
            
            Định dạng đầu ra phải là một JSON array, mỗi đối tượng trong array có cấu trúc:
            {{
                "title": "Tiêu đề nội dung đề xuất",
                "description": "Mô tả ngắn gọn về nội dung và lý do đề xuất",
                "type": "Loại tài liệu",
                "level": "Mức độ phù hợp",
                "relevance_reason": "Lý do tại sao nội dung này liên quan đến chủ đề gốc"
            }}
            
            Dựa vào những gì người dùng đã quan tâm trong ngữ cảnh, hãy cung cấp đề xuất thực sự phù hợp và có giá trị.
            """
        )
        
        # Create a chain for recommendation generation
        self.recommendation_chain = (
            {
                "topic": RunnablePassthrough(),
                "context": RunnablePassthrough(),
                "num_recommendations": RunnablePassthrough()
            }
            | self.recommendation_prompt
            | self.llm
            | JsonOutputParser()
        )

    async def __call__(self, topic: str, context: str = "", num_recommendations: int = 3) -> Dict:
        """
        Generates content recommendations based on a topic and context.
        
        :param topic: The main topic or lesson the user is interested in
        :param context: Additional context from the conversation (optional)
        :param num_recommendations: Number of recommendations to generate
        :return: Dictionary with recommendations in JSON format
        """
        try:
            result = await self.recommendation_chain.ainvoke({
                "topic": topic, 
                "context": context, 
                "num_recommendations": num_recommendations
            })
            print("đang dùng hàm content_recommender")
            return {"recommendations": result}
        except Exception as e:
            return {
                "recommendations": [], 
                "error": f"Không thể tạo gợi ý nội dung: {e}"
            } 