from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

class StartNode:
    def __call__(self, state):
        """Phương thức đồng bộ cho StartNode"""
        # pass-through
        return state
        
    async def __call__(self, state):
        """Phương thức bất đồng bộ cho StartNode"""
        # pass-through
        return state

class EndNode:
    def __call__(self, state):
        """Phương thức đồng bộ cho EndNode"""
        return state
        
    async def __call__(self, state):
        """Phương thức bất đồng bộ cho EndNode"""
        return state

class ReflectionNode:
    def __init__(self, llm, max_loops=3):
        self.llm = llm
        self.max_loops = max_loops
        self.reflection_prompt = PromptTemplate.from_template(
            """Bạn là một trợ lý AI. Hãy đánh giá câu trả lời sau đây đã đáp ứng đúng và đủ yêu cầu của người dùng chưa. 
            Nếu chưa, hãy trả về 'NO'.
            Nếu đã đủ, trả về 'YES'.\n\nTruy vấn của người dùng: {user_input}\nCâu trả lời của trợ lý: {assistant_response}\n\nĐánh giá (YES/NO):"""
        )
        self.reflection_chain = self.reflection_prompt | self.llm | StrOutputParser()
        self.refine_prompt = PromptTemplate.from_template(
            """Bạn là một trợ lý AI. Câu trả lời sau đây chưa đáp ứng đúng và đủ yêu cầu của người dùng.\nHãy viết lại truy vấn cho rõ ràng, cụ thể hơn để trợ lý có thể trả lời tốt hơn và hãy gợi ý search web.\nTruy vấn gốc của người dùng: {user_input}\nCâu trả lời trước đó của trợ lý: {assistant_response}\nTruy vấn đã làm rõ (bằng ngôn ngữ query của user, ngắn gọn, rõ ý, tập trung vào yêu cầu chính):"""
        )
        self.refine_chain = self.refine_prompt | self.llm | StrOutputParser()

    def __call__(self, state):
        """Phương thức đồng bộ cho ReflectionNode"""
        # Lưu ý: Chúng ta đang sử dụng phương thức đồng bộ của LLM trong môi trường đồng bộ
        # Điều này có thể gây ra vấn đề với một số mô hình chỉ hỗ trợ API bất đồng bộ
        print("USE REFLECTION NODE (SYNC)")
        user_input = state.get("input", "")
        messages = state.get("messages", [])
        assistant_response = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                assistant_response = msg.content
                break
                
        # Reflection loop count
        loop_count = state.get("reflection_loops", 0)
        
        # Nếu phương thức đồng bộ của LLM không khả dụng, chỉ cần trả về state hiện tại
        # Điều này sẽ giúp tránh lỗi nhưng có thể bỏ qua phản hồi
        state["needs_reflection"] = False
        state["reflection_loops"] = 0
        state["input_refine"] = None
        
        return state
        
    async def __call__(self, state):
        """Phương thức bất đồng bộ cho ReflectionNode"""
        print("USE REFLECTION NODE (ASYNC)")
        user_input = state.get("input", "")
        messages = state.get("messages", [])
        assistant_response = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                assistant_response = msg.content
                break
        # Reflection loop count
        loop_count = state.get("reflection_loops", 0)
        # Ask LLM if answer is satisfactory
        reflection = await self.reflection_chain.ainvoke({
            "user_input": user_input,
            "assistant_response": assistant_response
        })
        reflection = reflection.strip().upper()
        if reflection == "YES" or loop_count >= self.max_loops:
            state["needs_reflection"] = False
            state["reflection_loops"] = 0
            state["input_refine"] = None
        else:
            state["needs_reflection"] = True
            state["reflection_loops"] = loop_count + 1
            # Generate a clarified/reprompted input
            refined_input = await self.refine_chain.ainvoke({
                "user_input": user_input,
                "assistant_response": assistant_response
            })
            state["input_refined"] = refined_input.strip()
        return state