# src/tools/quiz_generator.py
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List, Optional

class QuizGeneratorTool:
    name = "quiz_generator"
    description = "Generate history quiz questions. Can generate multiple-choice questions with options and an answer, or open-ended questions without options and answer."

    def __init__(self, llm):
        self.llm = llm
        # Define the prompt for generating quiz questions
        self.quiz_prompt = PromptTemplate.from_template(
            """Bạn là một giáo viên lịch sử chuyên nghiệp.
            Tạo {num_q} câu hỏi lịch sử về chủ đề: {topic}.
            Nếu 'type' là 'multiple_choice', mỗi câu hỏi phải là trắc nghiệm với 4 lựa chọn (A, B, C, D) và chỉ một đáp án đúng.
            Nếu 'type' là 'open_ended', mỗi câu hỏi phải là câu hỏi mở không có lựa chọn và đáp án.

            Định dạng đầu ra phải là một JSON array, mỗi đối tượng trong array có cấu trúc:
            Nếu là trắc nghiệm:
            {{
                "question": "Câu hỏi?",
                "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
                "answer": "Đáp án đúng (A, B, C, hoặc D)"
            }}
            Nếu là câu hỏi mở:
            {{
                "question": "Câu hỏi?"
            }}

            Ví dụ câu hỏi trắc nghiệm:
            [
              {{
                "question": "Ai là vị hoàng đế đầu tiên của triều đại nhà Đinh?",
                "options": ["A. Đinh Bộ Lĩnh", "B. Lê Hoàn", "C. Lý Thái Tổ", "D. Trần Thái Tông"],
                "answer": "A"
              }}
            ]
            Ví dụ câu hỏi mở:
            [
              {{
                "question": "Nêu vai trò của sông Bạch Đằng trong lịch sử Việt Nam?"
              }}
            ]
            Loại câu hỏi: {type}
            """
        )
        # Create a chain for quiz generation
        self.quiz_chain = (
            {
                "topic": RunnablePassthrough(),
                "num_q": RunnablePassthrough(),
                "type": RunnablePassthrough() # Thêm 'type' vào input
            }
            | self.quiz_prompt
            | self.llm
            | JsonOutputParser() # JsonOutputParser sẽ tự động xử lý Optional fields
        )

    async def __call__(self, topic: str, num_q: int = 3, question_type: str = "multiple_choice"):
        """
        Generates quiz questions.
        :param topic: The historical topic for the quiz.
        :param num_q: Number of questions to generate.
        :param question_type: 'multiple_choice' for trắc nghiệm or 'open_ended' for câu hỏi mở.
        """
        try:
            result = await self.quiz_chain.ainvoke({"topic": topic, "num_q": num_q, "type": question_type})
            print("đang dùng hàm quiz_generator")
            return {"quiz": result}
        except Exception as e:
            return {"quiz": [], "error": f"Failed to generate quiz: {e}"}