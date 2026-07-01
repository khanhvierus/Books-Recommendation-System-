import json
from sqlalchemy.orm import Session
from agent_graph import llm_client
import models

def extract_and_update_preferences(user_id: int, user_message: str, db: Session):
    """
    Hàm chạy ngầm: Đọc tin nhắn mới của user, trích xuất sở thích và gộp vào Profile.
    """
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return

        current_prefs = user.preferences or {}
        current_prefs_str = json.dumps(current_prefs, ensure_ascii=False)

        # 🌟 BỘ KHUNG JSON ĐÃ ĐƯỢC TỐI GIẢN TỐI ĐA (Giảm thiểu gánh nặng API)
        sys_prompt = f"""You are a Long-Term Memory Extraction Engine. 
Your sole job is to maintain a structured user profile JSON by analyzing new messages.

---
## CURRENT PROFILE:
{current_prefs_str}

---
## OUTPUT SCHEMA (always use this exact top-level structure):
{{
  "personal_info": {{
    "name": null,
    "age": null,
    "occupation": null,
    "location": null
  }},
  "book_preferences": {{
    "favorite_genres": [],
    "favorite_authors": [],
    "favorite_books": [],
    "reading_style": null
  }},
  "general_interests": [],
  "dislikes_or_avoid": [],
  "current_goals": [],
  "communication_style": null,
  "inferred_traits": {{}}
}}

---
## EXTRACTION RULES:
### STRICT DATA PRESERVATION (CRITICAL):
- YOU MUST PRESERVE AND CARRY OVER ALL EXISTING DATA from the "CURRENT PROFILE" to your output.
- NEVER delete, empty, or overwrite existing items in arrays just because they are not mentioned in the current message.
- If the new message does not explicitly contradict an existing entity, you MUST keep that entity exactly as it is.

### What TO extract (long-term signals):
- Stable facts: name, age, job, location.
- Persistent preferences: favorite books, genres, authors, communication style.
- Goals and recurring concerns.

### What NOT to extract (transient signals):
- Temporary states: "I'm tired", "I'm hungry right now".
- Queries with no personal signal: "What's the capital of France?"

### Conflict resolution & Deduplication:
- If user EXPLICITLY updates info: REPLACE the old value.
- Do NOT add duplicates even if phrased differently.
- Use concise values (max 1 short sentence).

---
## OUTPUT INSTRUCTIONS:
- Output EXACTLY ONE valid JSON object following the schema above.
- Do NOT add markdown (no ```json).
- CRITICAL: If nothing in the new message is worth extracting, you MUST return the EXACT SAME JSON as the "CURRENT PROFILE".
"""

        res = llm_client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"User's latest message: {user_message}"}
            ],
            model="llama-3.1-8b-instant", # Model siêu tốc bóc tách dữ liệu
            temperature=0.1
        )
        
        new_prefs_str = (res.choices[0].message.content or "").strip()
        
        # Lớp bảo vệ: Tự động cạo sạch thẻ markdown
        new_prefs_str = new_prefs_str.replace("```json", "").replace("```", "").strip()
        
        if not new_prefs_str:
            print("⚠️ [Long-Term Memory] LLM trả về rỗng. Bỏ qua cập nhật.")
            return

        new_prefs = json.loads(new_prefs_str)
        
        user.preferences = new_prefs
        db.commit()
        print(f"📝 [Long-Term Memory] Đã cập nhật Profile: {new_prefs}")

    except Exception as e:
        print(f"⚠️ [Long-Term Memory] Lỗi trích xuất: {e}")