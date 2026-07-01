import uuid
from datetime import datetime
from qdrant_client.models import Filter, FieldCondition, MatchValue

class SemanticMemory:
    def __init__(self, qdrant_client, embed_model):
        self.qdrant = qdrant_client
        self.model = embed_model # model BAAI/bge-m3 của bạn
        self.collection = "chat_memory"

    def save_memory(self, user_id, session_id, user_message, ai_response):
        # 1. Gộp nội dung để AI dễ hiểu ngữ cảnh trọn vẹn
        memory_text = f"User : {user_message}\nAI Assistant: {ai_response}"
        
        # 2. Băm văn bản thành Vector
        vector = self.model.encode(memory_text).tolist()
        
        # 3. Đóng gói Metadata
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "text": memory_text,
            "timestamp": datetime.now().isoformat()
        }
        
        # 4. Lưu vào Qdrant
        self.qdrant.upsert(
            collection_name=self.collection,
            points=[
                {
                    "id": str(uuid.uuid4()), # ID ngẫu nhiên
                    "vector": vector,
                    "payload": payload
                }
            ]
        )

    def retrieve_memory(self, user_id, session_id, current_query, top_k=2):
        # 1. Nhúng câu hỏi hiện tại
        query_vector = self.model.encode(current_query).tolist()
        
        # 2. Tìm kiếm ký ức cũ bằng API mới (query_points)
        search_result = self.qdrant.query_points(
            collection_name=self.collection,
            query=query_vector, # Lưu ý: dùng 'query' thay vì 'query_vector'
            query_filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="session_id", match=MatchValue(value=session_id))
                ]
            ),
            limit=top_k,
            score_threshold=0.5
        ).points # Thêm .points để lấy mảng kết quả
        
        if not search_result:
            return ""
            
        # 3. Gộp các ký ức lại
        memories = [hit.payload["text"] for hit in search_result]
        return "\n---\n".join(memories)