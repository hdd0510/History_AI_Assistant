// Khởi tạo database và user cho ứng dụng
db = db.getSiblingDB('history_ai');

// Tạo user cho ứng dụng với quyền readWrite trên database history_ai
db.createUser({
  user: 'app_user',
  pwd: 'app_password',
  roles: [
    {
      role: 'readWrite',
      db: 'history_ai'
    }
  ]
});

// Tạo collections cần thiết
db.createCollection('checkpoints');
db.createCollection('user_profile');
db.createCollection('chat_history');

print('MongoDB initialized successfully!'); 