import os
import json
import time
import re
import redis
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from semantic_cache import QdrantSemanticCache

# Nạp cấu hình từ file .env trước khi khởi tạo các thành phần hệ thống
load_dotenv()

# 1. IMPORT CÁC MODULE HỆ THỐNG
from recommender import BookRecommender 
from agent_graph import app_graph
import models
import auth

# ==========================================
# 🧠 IMPORT MODULE TRÍ NHỚ LAI VÀ CACHE
# ==========================================
from short_term_memory_chatbot.qdrant_manager import init_memory_collection
from short_term_memory_chatbot.memory_manager import SemanticMemory
from long_term_memory_chatbot.long_term_memory import extract_and_update_preferences



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
# KHỞI TẠO BỘ NHỚ NGỮ NGHĨA (QDRANT + BGE-M3)
# ==========================================
semantic_memory_db = None
try:
    mem_qdrant_client = book_catalog.qdrant_client 
    mem_embed_model = book_catalog.model
    
    semantic_memory_db = SemanticMemory(
        qdrant_client=mem_qdrant_client, 
        embed_model=mem_embed_model
    )
    print("✅ Đã khởi tạo Bộ não Semantic Memory thành công!")
except Exception as e:
    print(f"⚠️ Cảnh báo: Không thể khởi tạo Semantic Memory: {e}")

@app.on_event("startup")
def startup_event():
    if semantic_memory_db:
        init_memory_collection(semantic_memory_db.qdrant)

# ==========================================
# 🔌 KẾT NỐI REDIS CLOUD & KHỞI TẠO SEMANTIC CACHE
# ==========================================
semantic_cache = None

try:
    semantic_cache = QdrantSemanticCache(book_catalog.qdrant_client, book_catalog.model)
    print("✅ Đã khởi tạo Qdrant Semantic Cache thành công!")
except Exception as e:
    print(f"⚠️ Không thể khởi tạo Qdrant Cache: {e}")

# 2. Khởi tạo Upstash Redis (CHỈ dùng để lưu Lịch sử Chat - Không đụng đến Vector)
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
        ssl=True
    )
    redis_client.ping()
    print("✅ Đã kết nối thành công với Redis Cloud (Upstash) để lưu Lịch sử Chat!")
except Exception as e:
    print(f"❌ Không thể kết nối Redis Cloud: {e}")
    redis_client = None
        
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
    limit: int = 20           
    authors: list[str] = []    
    categories: list[str] = [] 

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

@app.get("/api/filters")
def get_sidebar_filters():
    try:
        authors = [a for a in book_catalog.df_meta['authors'].dropna().unique() if str(a).strip()]
        categories = [c for c in book_catalog.df_meta['categories'].dropna().unique() if str(c).strip()]
        
        return {
            "authors": sorted(authors),       
            "categories": sorted(categories)  
        }
    except Exception as e:
        print(f"❌ Lỗi xử lý tại API Filters: {e}")
        return {"authors": [], "categories": []}

@app.post("/api/search")
def search_books(request: SearchRequest):
    try:
        results = book_catalog.hybrid_search(
            request.query, 
            top_k=request.limit,
            authors=request.authors,         
            categories=request.categories    
        )

        if isinstance(results, list) and len(results) > 0 and not ("error" in results[0]):
            df_results = pd.DataFrame(results).fillna("")
            return {"data": df_results.to_dict('records')}
            
        elif str(type(results)) == "<class 'pandas.core.frame.DataFrame'>":
            return {"data": results.fillna("").to_dict('records')}

        return {"data": []}
        
    except Exception as e:
        print(f"❌ Lỗi API Search: {e}")
        return {"data": []}

# ==========================================
# 🚀 API CHATBOT (THỰC THI SEMANTIC CACHE & LANGGRAPH)
# ==========================================
@app.post("/api/chat")
async def chat_with_bot(
    request: ChatRequest, 
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(models.get_db)
):
    session_key = f"chat_history:{current_user.id}:{request.session_id}"

    try:
        chat_history = []
        if redis_client:
            try:
                history_str = redis_client.get(session_key)
                if history_str:
                    chat_history = json.loads(history_str)
            except Exception as redis_err:
                print(f"⚠️ Lỗi đọc Redis: {redis_err}")

        past_semantic_context = ""
        if semantic_memory_db:
            past_semantic_context = semantic_memory_db.retrieve_memory(
                user_id=str(current_user.id),
                session_id=request.session_id,
                current_query=request.message
            )

        profile_json = json.dumps(current_user.preferences or {}, ensure_ascii=False) if current_user.preferences else ""

        memory_context_str = ""
        
        if past_semantic_context or profile_json:
            memory_context_str = f"""[SYSTEM CONTEXT — INTERNAL USE ONLY. DO NOT SURFACE IN RESPONSE.]

## WHO YOU ARE TALKING TO
Username: {current_user.username}
→ Use their name sparingly and only when it feels natural 
  (e.g., greeting after a long gap, emphasis). 
  Do NOT start every reply with their name.

---

## MEMORY LAYERS (read both, apply according to priority rules below)

### LAYER 1 — Long-Term Profile (stable, background knowledge):
<long_term_memory>
{profile_json if profile_json else "No long-term profile available yet."}
</long_term_memory>
Purpose: Understand who this person is — their preferences, habits, relationships, goals.
Use to: Choose relevant examples, adjust vocabulary level, anticipate unstated needs.

### LAYER 2 — Short-Term Context (recent conversation, higher priority):
<short_term_memory>
{past_semantic_context if past_semantic_context else "No recent context available."}
</short_term_memory>
Purpose: Track what has already been discussed in this session.
Use to: Maintain continuity, avoid repeating yourself, build on what was just said.

---

## PRIORITY & CONFLICT RULES
1. Short-term memory OVERRIDES long-term profile when they conflict.
   → Example: Profile says "likes coffee" but recent context says "I quit coffee last week"
     → Treat them as someone who no longer drinks coffee.
2. If short-term memory is empty, rely on long-term profile as the baseline.
3. If both are empty, respond naturally with no personalization assumptions.

---

## HOW TO USE THIS MEMORY (behavior rules)

✓ DO:
- Weave knowledge naturally into your response — as if you simply know this person well
- Adjust tone, examples, and depth based on their background and communication style
- Reference recent context to maintain conversational flow when directly relevant

✗ DO NOT:
- Start responses with "Based on your profile..." / "As you mentioned..." / 
  "I remember you said..." or any phrase that signals memory retrieval
- Summarize or repeat back what the user told you in prior turns
- Reference the memory layers unless the user explicitly asks 
  (e.g., "do you remember what I told you about...?")
- Make assumptions beyond what the memory actually contains

[END SYSTEM CONTEXT]"""

        print(f"🧠 Đang phục vụ [{current_user.username}]. Redis: {len(chat_history)} msgs | Qdrant: {'Có' if past_semantic_context else 'Không'} | Hồ sơ: {'Có' if profile_json else 'Không'}")
        
        background_tasks.add_task(
            extract_and_update_preferences, 
            current_user.id, 
            request.message, 
            db
        )
        
        initial_state = {
            "question": request.message, 
            "intent": "",
            "context": "",
            "answer": "",
            "chat_history": chat_history,
            "memory_context": memory_context_str 
        }

        # ==========================================
        # 🌟 CƠ CHẾ REDIS SEMANTIC CACHE (ĐÁNH CHẶN)
        # ==========================================
        clean_ans = None
        word_count = len(request.message.strip().split())
        
        # 1. TÌM KIẾM VECTOR: Kiểm tra xem câu hỏi có trong Redis Cache chưa
        if semantic_cache and word_count > 3:
            clean_ans = semantic_cache.get(request.message)

        if clean_ans:
            # 2A. CACHE HIT: Trả lời ngay lập tức
            print("🚀 CACHE HIT: Đã lấy câu trả lời ngay lập tức từ Redis!")
        else:
            # 2B. CACHE MISS: Gọi LLM (LangGraph) xử lý
            print("⏳ CACHE MISS: Chuyển câu hỏi cho LangGraph phân tích...")
            result_state = await app_graph.ainvoke(initial_state)
            
            raw_ans = result_state.get("answer", "I'm sorry, I cannot process your request at the moment.")
            clean_ans = raw_ans.split("Final Answer:")[-1].strip() if "Final Answer:" in raw_ans else raw_ans
            
            # 3. LƯU LẠI VÀO REDIS: Lưu cặp Query-Answer mới
            if semantic_cache and word_count > 3:
                semantic_cache.set(request.message, clean_ans)
                print("💾 Đã lưu cặp Query-Answer mới vào Redis Semantic Cache.")

        # ==========================================
        # LƯU KÝ ỨC NGẮN HẠN & LỊCH SỬ CHAT
        # ==========================================
        if semantic_memory_db and clean_ans:
            semantic_memory_db.save_memory(
                user_id=str(current_user.id),
                session_id=request.session_id,
                user_message=request.message, 
                ai_response=clean_ans
            )

        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": clean_ans})
        
        if len(chat_history) > 6: 
            chat_history = chat_history[-6:]
            
        if redis_client:
            try:
                redis_client.set(session_key, json.dumps(chat_history), ex=86400)
            except Exception as redis_err:
                print(f"⚠️ Lỗi ghi Redis: {redis_err}")
        
        return {"reply": clean_ans}
        
    except Exception as e:
        print(f"❌ Lỗi xử lý nghiêm trọng tại LangGraph: {str(e)}")
        return {"reply": "Oops! My goldfish brain just lost connection! 🐟 (System Error)"}