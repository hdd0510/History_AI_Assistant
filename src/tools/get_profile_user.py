from typing import Dict, Optional
import os
import threading
import msgpack
from datetime import datetime
import pymongo

# For LLM summarization with Gemini
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI


class GetProfileUserTool:
    def __init__(self, user_id: str):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.user_id = user_id
        
        # Initialize MongoDB connection directly
        client = pymongo.MongoClient(self.mongo_uri)
        db_name = self.mongo_uri.split("/")[-1].split("?")[0]
        self.db = client[db_name]
        self.user_profile = self.db["user_profile"]
        print("Type of self.user_profile:", type(self.user_profile))

    async def _summarize_with_gemini(self, messages, existing_profile=None):
        """
        Use Gemini to summarize user profile based on their messages and existing profile if available
        """
        messages_content = [m.get("content", "") for m in messages if m.get("content")]
        
        # Include only the most recent messages if we're updating
        recent_messages = messages_content[-min(20, len(messages_content)):]
        
        system_prompt = "You are an AI assistant that analyzes user messages to build a profile. " \
                        "Identify key information such as interests, preferences, demographic info, " \
                        "and personality traits from the messages provided."
        
        if existing_profile:
            # If we have an existing profile, use it for context
            prompt = f"{system_prompt}\n\nCurrent profile summary: {existing_profile.get('summary', '')}\n\n" \
                     f"Based on these new messages AND the existing profile, create an updated user profile summary.\n\n" \
                     f"Recent Messages: {recent_messages}"
        else:
            # Initial profile creation
            prompt = f"{system_prompt}\n\nBased on these messages, create a concise user profile summary about the person.\n\n" \
                     f"Messages: {messages_content[:20]}"
        
        # Use langchain Gemini model to generate content
        response = await self.model.ainvoke(prompt)
        
        # Create structured profile with extracted information
        profile_data = {
            "summary": response.content,
            "last_updated": datetime.now(),
            "message_count": len(messages),
        }
        
        return profile_data

    async def build_profile_from_history(self):
        """
        Build profile từ history conversation (MongoDB collection: checkpoints).
        Chỉ tạo profile nếu có ít nhất 5 messages.
        Cập nhật profile sau mỗi 10 message mới, kết hợp thông tin từ profile cũ.
        """
        try:
            profiles    = self.user_profile
            existing_profile = user.get("profile") if user else None
            current_message_count = user.get("processed_message_count", 0) if user else 0
            
            # Tìm các checkpoint có chứa user_id trong messages
            checkpoints = self.db["checkpoints"]
            cursor = checkpoints.find({})
            messages = []
            
            for doc in cursor:
                raw = doc.get("checkpoint")
                if raw is None:
                    continue
                try:
                    checkpoint = msgpack.unpackb(raw, raw=False)
                except Exception:
                    continue
                for m in checkpoint.get("messages", []):
                    # Chỉ lấy message từ user_id này
                    if m.get("role") == "user" and m.get("user_id") == self.user_id:
                        messages.append(m)
            
            # Check if we have enough messages
            total_messages = len(messages)
            
            # Create or update profile based on thresholds
            should_update = False
            
            # Case 1: No profile yet, but we have enough messages
            if not existing_profile and total_messages >= self.MIN_MESSAGES_FOR_PROFILE:
                should_update = True
            
            # Case 2: We have a profile, but there are 10+ new messages since last update
            elif existing_profile and (total_messages - current_message_count) >= self.UPDATE_PROFILE_THRESHOLD:
                should_update = True
                
            if should_update:
                # Generate profile with Gemini, including existing profile data for updates
                profile_data = await self._summarize_with_gemini(messages, existing_profile)
                
                # Update user document
                self.db.users.update_one(
                    {"_id": self.user_id}, 
                    {
                        "$set": {
                            "profile": profile_data,
                            "processed_message_count": total_messages,
                            "last_updated": datetime.now()
                        }
                    },
                    upsert=True
                )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error building profile: {e}")
            return False

    def start_background_profile_building(self):
        """
        Starts the profile building process in a background thread
        """
        def run_async_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.build_profile_from_history())
            loop.close()
            
        # Start in background thread
        thread = threading.Thread(target=run_async_in_thread)
        thread.daemon = True
        thread.start()

    async def __call__(self) -> Dict:
        """
        Trả về dict thông tin profile hoặc thông báo không tìm thấy.
        """
        # Tìm user từ MongoDB
        user = self._get_from_mongo()
        
        # Nếu tìm thấy user và có profile
        if user and not user.get("error") and user.get("profile"):
            return {"profile": user}
        
        # Nếu có lỗi
        if user and user.get("error"):
            return user
            
        # Nếu không tìm thấy user hoặc user chưa có profile,
        # khởi động quá trình build profile trong background
        self.start_background_profile_building()
        
        if user and not user.get("profile"):
            return {
                "message": f"Đã tìm thấy user với ID '{self.user_id}' nhưng chưa có profile. "
                          f"Hệ thống đang tiến hành xây dựng profile (cần ít nhất {self.MIN_MESSAGES_FOR_PROFILE} messages). "
                          f"Vui lòng thử lại sau."
            }
        else:
            return {
                "message": f"Không tìm thấy user với ID '{self.user_id}' trong database. "
                          f"Đang tiến hành xây dựng profile nếu có đủ {self.MIN_MESSAGES_FOR_PROFILE} messages. "
                          f"Vui lòng thử lại sau."
            } 

if __name__ == "__main__":
    # Example usage
    tool = GetProfileUserTool(user_id="1")
    profile_info = tool()
    print(profile_info)