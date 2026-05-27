import pandas as pd
from sentence_transformers import SentenceTransformer
import os
from thefuzz import process
from qdrant_client import QdrantClient

class BookRecommender:
    def __init__(self):
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        qdrant_path = os.path.join(CURRENT_DIR, "data", "qdrant_db")
        csv_path = os.path.join(CURRENT_DIR, "data", "books_metadata.csv") 

        # 1. KHỞI TẠO QDRANT 
        # self.qdrant_client = QdrantClient(path=qdrant_path)
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_HOST"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=60
        )
        self.collection_name = "book_metadata_collection"
        
        # 2. KHỞI TẠO MÔ HÌNH BGE-M3 (SOTA Multi-lingual, 1024 chiều)
        self.model = SentenceTransformer("BAAI/bge-m3")
        
        # 3. GIỮ LẠI PANDAS CHỈ ĐỂ PHỤC VỤ FUZZY MATCH
        self.df_meta = pd.read_csv(csv_path)
        self.df_meta['title'] = self.df_meta['title'].fillna('Unknown Title')
        self.all_titles = self.df_meta['title'].tolist()

    # ========================================================
    # CHỨC NĂNG 1: RECOMMEND BASED ON IDEA (Two-Stage Retrieval)
    # ========================================================
    def search_by_idea(self, user_query, top_k=15):
        """
        Giai đoạn 1: Lấy rộng 15 cuốn sách thô bằng Vector Search (Qdrant).
        Sẽ được đưa qua Cross-Encoder chấm điểm lại ở agent_graph.py.
        """
        query_vector = self.model.encode(user_query).tolist()
        
        search_results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k
        ).points
        
        results = []
        for hit in search_results:
            # Gộp thông tin thành 1 đoạn văn bản để Cross-Encoder dễ dàng đọc hiểu
            combined_text = f"Title: {hit.payload.get('title', '')}. Author: {hit.payload.get('authors', '')}. Summary: {hit.payload.get('short_summary', '')}"
            
            results.append({
                'text': combined_text, # Key bắt buộc cho hàm rerank_cross_encoder
                'title': hit.payload.get('title', ''),
                'authors': hit.payload.get('authors', ''),
                'categories': hit.payload.get('categories', ''),
                'short_summary': hit.payload.get('short_summary', ''),
                'average_rating': hit.payload.get('average_rating', 0.0),
                'thumbnail': hit.payload.get('thumbnail', ''),
                'qdrant_score': hit.score 
            })
        return results

    # ========================================================
    # CHỨC NĂNG 2: RECOMMEND BASED ON ITEM (Fuzzy + Vector)
    # ========================================================
    def get_similar_books(self, book_title, top_k=5):
        """
        BƯỚC 1: Dùng Fuzzy Match để tìm chính xác tên sách (sửa lỗi gõ sai).
        BƯỚC 2: Dùng Vector Search tìm sách tương tự, tự loại bỏ sách gốc.
        """
        best_match, score = process.extractOne(book_title, self.all_titles)
        
        if score < 60:
            return {"error": f"❌ Không tìm thấy sách nào gần giống với '{book_title}' trong thư viện."}
            
        target_title = best_match
        print(f"\n🎯 [Fuzzy Match] Nhận diện sách gốc: '{target_title}' (Độ tự tin: {score}%)")
        
        query_vector = self.model.encode(target_title).tolist()
        
        # Lấy dư ra vài cuốn để phòng trừ Qdrant trả về chính cuốn sách gốc
        search_results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k + 3 
        ).points
        
        results = []
        seen_titles = set([target_title.lower().strip()]) 
        
        for hit in search_results:
            title = hit.payload.get('title', '')
            clean_title = title.lower().strip()
            
            if clean_title in seen_titles:
                continue
                
            seen_titles.add(clean_title)
            results.append({
                'title': title,
                'authors': hit.payload.get('authors', ''),
                'categories': hit.payload.get('categories', ''),
                'short_summary': hit.payload.get('short_summary', ''),
                'average_rating': hit.payload.get('average_rating', 0.0),
                'thumbnail': hit.payload.get('thumbnail', ''),
                'ai_score': hit.score
            })
            
            if len(results) >= top_k:
                break
                
        return results