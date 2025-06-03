from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["chatbot_fpt"]
collection = db["users"]

new_user = {"name": "Bob", "age": 22}
collection.insert_one(new_user)
print("Inserted user with ID:", collection.inserted_id)

# ✅ Tìm tất cả user
print("📋 Danh sách user:")
for user in collection.find():
    print(user)

# # ✅ Tìm theo điều kiện
# print("🔍 Tìm user có tên Alice:")
# user = collection.find_one({"name": "Alice"})
# print(user)

# # ✅ Update user
# collection.update_one({"name": "Alice"}, {"$set": {"age": 30}})
# print("✅ Đã cập nhật tuổi Alice lên 30")

# # ✅ Xoá user
# collection.delete_one({"name": "Alice"})
# print("🗑️ Đã xoá user Alice")
