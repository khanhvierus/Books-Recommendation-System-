import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

class QdrantSemanticCache:
    def __init__(self, qdrant_client: QdrantClient, embed_model, threshold=0.8):
        self.qdrant = qdrant_client
        self.embed_model = embed_model
        # Ngưỡng tin cậy (0.80 = Giống 80% trở lên mới tính là HIT)
        self.threshold = threshold
        self.collection_name = "semantic_cache_collection"
        self._setup_collection()

    def _setup_collection(self):
        try:
            # Kiểm tra xem collection đã tồn tại chưa
            self.qdrant.get_collection(self.collection_name)
        except Exception:
            print("⚙️ Đang tạo Collection mới cho Qdrant Semantic Cache...")
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest_models.VectorParams(
                    size=1024,  # Số chiều của BGE-M3
                    distance=rest_models.Distance.COSINE
                )
            )

    def get(self, query: str):
        # 1. Nhúng câu hỏi thành vector
        vector = self.embed_model.encode(query).tolist()
        
        # 🌟 ĐÃ SỬA: Dùng query_points thay vì search để tương thích với Qdrant Client mới
        search_result = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=1
        ).points
        
        if search_result:
            best_hit = search_result[0]
            if best_hit.score >= self.threshold:
                print(f"🎯 [Semantic Cache] HIT! Similarity: {best_hit.score:.4f} | Câu hỏi cũ: '{best_hit.payload.get('query_text')}'")
                return best_hit.payload.get("response")
            else:
                print(f"📉 [Semantic Cache] MISS! Max similarity: {best_hit.score:.4f} (Chưa đạt ngưỡng {self.threshold})")
        return None

    def set(self, query: str, response: str):
        vector = self.embed_model.encode(query).tolist()
        
        # Qdrant yêu cầu ID là số nguyên (Integer) hoặc UUID. Ta băm câu hỏi ra một số nguyên.
        point_id = int(hashlib.md5(query.encode('utf-8')).hexdigest()[:15], 16)
        
        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=[
                rest_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "query_text": query,
                        "response": response
                    }
                )
            ]
        )