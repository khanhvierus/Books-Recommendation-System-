import os
import json
import time
import re
import redis
import pandas as pd # Đã bổ sung thư viện này để API search không bị lỗi
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Nạp cấu hình từ file .env trước khi khởi tạo các thành phần hệ thống
load_dotenv()

# 1. IMPORT CÁC MODULE HỆ THỐNG
from recommender import BookRecommender 
from agent_graph import app_graph
import models
import auth

# Khởi tạo bảng dữ liệu PostgreSQL khi khởi động hệ thống
models.init_db()

app = FastAPI(title="Smart Library API - Enterprise Edition")

# CẤU HÌNH CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Đang nạp dữ liệu Catalog Sách cho UI...")
book_catalog = BookRecommender()

# ==========================================
# 🔌 KẾT NỐI REDIS CLOUD (UPSTASH)
# ==========================================
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
        ssl=True
    )
    redis_client.ping()
    print("✅ Đã kết nối thành công với Redis Cloud!")
except Exception as e:
    print(f"❌ Không thể kết nối Redis Cloud: {e}")
    redis_client = None

# ==========================================
# CẤU TRÚC DỮ LIỆU ĐẦU VÀO (SCHEMAS)
# ==========================================
class UserRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLoginRequest(BaseModel):
    username: str
    password: str

class SearchRequest(BaseModel):
    query: str
    mode: str = "name"
    limit: int = 10

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

# ==========================================
# 🔐 HỆ THỐNG API XÁC THỰC (AUTH ENDPOINTS)
# ==========================================
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(request: UserRegisterRequest, db: Session = Depends(models.get_db)):
    db_user = db.query(models.User).filter(models.User.username == request.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Tên tài khoản đã tồn tại trên hệ thống")
        
    db_email = db.query(models.User).filter(models.User.email == request.email).first()
    if db_email:
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký sử dụng")
        
    hashed_pwd = auth.get_password_hash(request.password)
    new_user = models.User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_pwd
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Đăng ký tài khoản thành công!", "username": new_user.username}

@app.post("/api/auth/login")
def login_user(request: UserLoginRequest, db: Session = Depends(models.get_db)):
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user or not auth.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác")
        
    access_token = auth.create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user.username
    }

# ==========================================
# CÁC API DÀNH CHO GIAO DIỆN WEB (UI ENDPOINTS)
# ==========================================
@app.get("/api/random")
def get_random_books():
    safe_df = book_catalog.df_meta.sample(9).fillna("")
    return {"data": safe_df.to_dict('records')}

@app.post("/api/search")
def search_books(request: SearchRequest):
    try:
        # 1. Gọi đúng tên hàm trong recommender.py
        if request.mode == "name":
            results = book_catalog.get_similar_books(request.query, top_k=request.limit)
        else:
            # Sửa 'hybrid_search' thành 'search_by_idea'
            results = book_catalog.search_by_idea(request.query, top_k=request.limit)

        # 2. Xử lý an toàn dữ liệu trả về (Đảm bảo luôn là dạng list/dict)
        if isinstance(results, list) and len(results) > 0 and not ("error" in results[0]):
            import pandas as pd
            df_results = pd.DataFrame(results).fillna("")
            return {"data": df_results.to_dict('records')}
            
        elif str(type(results)) == "<class 'pandas.core.frame.DataFrame'>":
            # Đề phòng trường hợp hàm của bạn trả về thẳng DataFrame
            return {"data": results.fillna("").to_dict('records')}

        return {"data": []}
        
    except Exception as e:
        print(f"❌ Lỗi API Search: {e}")
        return {"data": []}


# ==========================================
# API CHATBOT BẢO MẬT (SỬ DỤNG AI CORE + TRÍ NHỚ REDIS)
# ==========================================
@app.post("/api/chat")
async def chat_with_bot(
    request: ChatRequest, 
    current_user: models.User = Depends(auth.get_current_user) # CHẶN CỬA: Bắt buộc đăng nhập
):
    # KẾT HỢP ID DATABASE VÀ SESSION ĐỂ CÔ LẬP TRÍ NHỚ NGƯỜI DÙNG
    session_key = f"chat_history:{current_user.id}:{request.session_id}"

    # LUỒNG TRÍ TUỆ NHÂN TẠO (ROUTING QUA LANGGRAPH + REDIS)
    try:
        chat_history = []
        
        if redis_client:
            try:
                history_str = redis_client.get(session_key)
                if history_str:
                    chat_history = json.loads(history_str)
            except Exception as redis_err:
                print(f"⚠️ Cảnh báo lỗi đọc dữ liệu từ Redis: {redis_err}")

        print(f"🧠 Đang phục vụ [{current_user.username}]. Lịch sử hiện hành: {len(chat_history)} tin nhắn.")
        
        initial_state = {
            "question": request.message,
            "intent": "",
            "context": "",
            "answer": "",
            "chat_history": chat_history 
        }
        
        result_state = await app_graph.ainvoke(initial_state)
        
        raw_ans = result_state.get("answer", "Xin lỗi, tôi không thể xử lý yêu cầu lúc này.")
        clean_ans = raw_ans.split("Final Answer:")[-1].strip() if "Final Answer:" in raw_ans else raw_ans
        
        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": clean_ans})
        
        if len(chat_history) > 6:
            chat_history = chat_history[-6:]
            
        if redis_client:
            try:
                redis_client.set(session_key, json.dumps(chat_history), ex=86400)
            except Exception as redis_err:
                print(f"⚠️ Cảnh báo lỗi ghi dữ liệu vào Redis: {redis_err}")
        
        return {"reply": clean_ans}
        
    except Exception as e:
        print(f"❌ Lỗi xử lý nghiêm trọng tại LangGraph: {str(e)}")
        return {"reply": "Oops! My goldfish brain just lost connection! 🐟 (Lỗi hệ thống AI)"}