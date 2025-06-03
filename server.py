from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Dữ liệu giả lập: danh sách user
users = {
    1: {"id": 1, "name": "Alice", "age": 25},
    2: {"id": 2, "name": "Bob", "age": 30},
    3: {"id": 3, "name": "Charlie", "age": 22},
}

# Schema cho phản hồi
class User(BaseModel):
    id: int
    name: str
    age: int

# ✅ API lấy thông tin user theo ID
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ✅ API xoá user theo ID
@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    deleted_user = users.pop(user_id)
    return {"message": f"User {deleted_user['name']} deleted successfully"}
