import requests
import time

# URL gốc của hệ thống
base_url = "http://127.0.0.1:8000/api"

# Thông tin tài khoản test
user_data = {
    "username": "alex_test_003",
    "email": "alex003@example.com",
    "password": "SecurePassword123"
}

print("="*50)
print("🚀 BẮT ĐẦU TEST LUỒNG BẢO MẬT HỆ THỐNG")
print("="*50)

# ------------------------------------------------
print("\n1. 📝 Tiến hành Đăng ký tài khoản...")
reg_res = requests.post(f"{base_url}/auth/register", json=user_data)
print(f"Phản hồi: {reg_res.json()}")

# ------------------------------------------------
print("\n2. 🔑 Tiến hành Đăng nhập lấy thẻ Token...")
login_res = requests.post(f"{base_url}/auth/login", json={
    "username": user_data["username"],
    "password": user_data["password"]
})
tokens = login_res.json()
print(f"Phản hồi: {tokens}")

access_token = tokens.get("access_token")

# ------------------------------------------------
if access_token:
    print("\n3. 💬 Thử nghiệm Chat với AI (có đính kèm Token)...")
    
    # Gắn thẻ Token vào Header của Request
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Câu hỏi thử thách trí nhớ
    chat_payload = {
        "message": "Hi, I am Alex. I love the Harry Potter series.", 
        "session_id": "tab_1"
    }
    
    print(f"👱 Gửi: {chat_payload['message']}")
    chat_res = requests.post(f"{base_url}/chat", json=chat_payload, headers=headers)
    print(f"🤖 AI Trả lời: {chat_res.json().get('reply')}")
    
    time.sleep(2)
    
    chat_payload_2 = {
        "message": "Do you remember my name and my favorite book series?", 
        "session_id": "tab_1"
    }
    print(f"\n👱 Gửi: {chat_payload_2['message']}")
    chat_res_2 = requests.post(f"{base_url}/chat", json=chat_payload_2, headers=headers)
    print(f"🤖 AI Trả lời: {chat_res_2.json().get('reply')}")

else:
    print("\n❌ Thất bại: Không lấy được thẻ JWT Token.")
    
print("\n" + "="*50)