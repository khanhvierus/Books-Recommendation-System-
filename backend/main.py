from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from recommender import BookRecommender 
import pandas as pd
import os
import time
from groq import Groq
import re
from dotenv import load_dotenv
import json
load_dotenv() 
app = FastAPI(title="Book RAG API")

# CẤU HÌNH CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. KHỞI TẠO AI VÀ GROQ
print("Đang nạp dữ liệu FAISS...")
ai_system = BookRecommender()

# LƯU Ý: Đảm bảo máy bạn đã có biến môi trường GROQ_API_KEY, 
# hoặc dán trực tiếp key vào đây (nhưng cẩn thận đừng push lên Github)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 2. CẤU TRÚC DỮ LIỆU TÌM KIẾM (Đã thêm biến mode)
class SearchRequest(BaseModel):
    query: str
    mode: str = "name" # "name" (fuzzy) hoặc "idea" (vector)
    limit: int = 10    # Yêu cầu 10 cuốn

# 3. CẤU TRÚC DỮ LIỆU CHATBOT
class ChatRequest(BaseModel):
    message: str
    history: list = [] # Lưu lịch sử chat

# ==========================================
# CÁC API ENDPOINTS
# ==========================================

@app.get("/api/random")
def get_random_books():
    # Lấy 9 cuốn để chia làm 3 hàng x 3 cột
    safe_df = ai_system.df_meta.sample(9).fillna("")
    return {"data": safe_df.to_dict('records')}

@app.post("/api/search")
def search_books(request: SearchRequest):
    # Chọn phương pháp tìm kiếm dựa vào mode từ Frontend gửi lên
    if request.mode == "name":
        # Tìm theo tên (Levenshtein)
        results = ai_system.fuzzy_search_title(request.query, limit=request.limit)
    else:
        # Tìm theo ý tưởng (Vector Hybrid)
        # Sửa lại hàm hybrid_search của bạn để lấy top_k=request.limit nếu cần
        results = ai_system.hybrid_search(request.query) 
        # Cắt lấy đúng 10 kết quả đầu tiên
        results = results[:request.limit] 

    # Lọc NaN trước khi trả về để tránh lỗi Internal Server Error
    if isinstance(results, list) and len(results) > 0 and not ("error" in results[0]):
        df_results = pd.DataFrame(results).fillna("")
        return {"data": df_results.to_dict('records')}
    
    return {"data": []}

@app.post("/api/chat")

def chat_with_bot(request: ChatRequest):
    user_msg_lower = request.message.lower()

    # ==========================================
    # 1. LUỒNG ĐẶC QUYỀN (VIP): KÝ ỨC VỀ NGỌC LINH
    # ==========================================
    # Nếu nhắc tới Ngọc Linh, bỏ qua AI, trả thẳng đoạn text gốc cứng cáp 100%
    if "ngọc linh" in user_msg_lower or "linh" in user_msg_lower:
        time.sleep(1)
        exact_memory = "Ngọc Linh, 18/07/2004. Là một cô gái dịu dàng, xinh đẹp, vô tư, đôi lúc hay quên. Cô ấy rất thích các món nước đậm đà (hủ tíu, bánh canh, bún riêu, bún bò,...), thích uống cafe đậm vị và trà sữa đậm vị, rất mê đồ uống Ngô Gia. Ngủ nhiều, hát hay (hay lạc tông), thích đi du lịch, xem văn nghệ."
        signature = "Tớ là Chatbot não cá vàng, tớ rất hay quên, nhưng mọi thứ về cậu, tớ sẽ luôn giữ trong ngăn sâu nhất của ký ức 💙💙💙"
        return {"reply": f"{exact_memory}\n\n{signature}"}


    # ==========================================
    # 2. LUỒNG BÌNH THƯỜNG: AI TƯ VẤN SÁCH
    # ==========================================
    match = re.search(r'(\d+)', request.message)
    requested_count = int(match.group(1)) if match else 3 
    fetch_count = min(max(requested_count, 3), 10) 

    context_books = ai_system.hybrid_search(request.message)[:fetch_count] 
    
    context_text = ""
    for i, b in enumerate(context_books):
        if isinstance(b, dict):
            img_url = b.get('thumbnail', '').replace("http://", "https://")
            if not img_url:
                img_url = "https://via.placeholder.com/150x220?text=No+Cover"
            
            context_text += f"\n[BOOK {i+1}]:\n"
            context_text += f"- Title: {b['title']}\n"
            context_text += f"- Author: {b.get('authors', 'Unknown')}\n"
            context_text += f"- Summary: {b.get('short_summary', 'No summary available')}\n"
            context_text += f"- URL: {img_url}\n"

    sys_prompt = f"""You are AI-CÁ VÀNG, a professional book assistant.
    
    DATA CONTEXT:
    {context_text}

    STRICT RULES:
    1. If the user chats normally (e.g., hello, thanks), reply naturally in ENGLISH without listing books.
    2. If recommending books, you MUST provide exactly {requested_count} books in ENGLISH.
    3. FORMATTING: You MUST use this EXACT format for each book (Do not wrap in code blocks). DO NOT include any images or URLs:
       
       **[Title]**
       - **Author:** [Author]
       - **Summary:** [Summary]
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": request.message}
            ],
            model="llama-3.1-8b-instant",
            max_tokens=1000
        )
        final_reply = response.choices[0].message.content.strip()
    except Exception as e:
        final_reply = "Oops! My goldfish brain just lost connection! 🐟"

    return {"reply": final_reply}