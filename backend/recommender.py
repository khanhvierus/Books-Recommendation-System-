import pandas as pd
from sentence_transformers import SentenceTransformer
import os
from thefuzz import process, fuzz
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

class BookRecommender:
    def __init__(self):
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        qdrant_path = os.path.join(CURRENT_DIR, "data", "qdrant_db")
        csv_path = os.path.join(CURRENT_DIR, "data", "books_metadata_new.csv") 

        # 1. KHỞI TẠO QDRANT 
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_HOST"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=60
        )
        self.collection_name = "book_metadata_collection"
        
        # 2. TẠO MỤC LỤC
        self._create_payload_indexes()
        
        # 3. KHỞI TẠO MÔ HÌNH BGE-M3
        self.model = SentenceTransformer("BAAI/bge-m3")
        
        # 4. ĐỌC DỮ LIỆU
        self.df_meta = pd.read_csv(csv_path)
        self.df_meta['title'] = self.df_meta['title'].fillna('Unknown Title')
        self.all_titles = self.df_meta['title'].tolist()
        
        # 🌟 5. TẠO BẢN ĐỒ TRA CỨU NHANH O(1) ĐỂ TRÁNH FUZZY MATCH
        self.exact_title_map = {title.strip().lower(): title for title in self.all_titles}

    def _create_payload_indexes(self):
        try:
            self.qdrant_client.create_payload_index(collection_name=self.collection_name, field_name="authors", field_schema=rest_models.PayloadSchemaType.KEYWORD)
            self.qdrant_client.create_payload_index(collection_name=self.collection_name, field_name="categories", field_schema=rest_models.PayloadSchemaType.KEYWORD)
            self.qdrant_client.create_payload_index(collection_name=self.collection_name, field_name="average_rating", field_schema=rest_models.PayloadSchemaType.FLOAT)
            print("✅ Đã kiểm tra/khởi tạo Payload Index (Authors, Categories, Rating) thành công.")
        except Exception as e:
            pass

    def _build_filter(self, authors: list, categories: list):
        must_conditions = []
        if authors:
            must_conditions.append(rest_models.FieldCondition(key="authors", match=rest_models.MatchAny(any=authors)))
        if categories:
            must_conditions.append(rest_models.FieldCondition(key="categories", match=rest_models.MatchAny(any=categories)))
        if must_conditions:
            return rest_models.Filter(must=must_conditions)
        return None

    def search_by_idea(self, user_query, top_k=20, authors=None, categories=None):
        query_filter = self._build_filter(authors, categories)
        
        if not user_query or not user_query.strip():
            try:
                records, _ = self.qdrant_client.scroll(
                    collection_name=self.collection_name, scroll_filter=query_filter, limit=top_k,
                    order_by=rest_models.OrderBy(key="average_rating", direction=rest_models.Direction.DESC), with_payload=True
                )
                search_results = records
            except Exception as e:
                records, _ = self.qdrant_client.scroll(collection_name=self.collection_name, scroll_filter=query_filter, limit=1000, with_payload=True)
                search_results = sorted(records, key=lambda x: x.payload.get('average_rating', 0), reverse=True)[:top_k]
        else:
            query_vector = self.model.encode(user_query).tolist()
            search_results = self.qdrant_client.query_points(
                collection_name=self.collection_name, query=query_vector, query_filter=query_filter, limit=top_k
            ).points
        
        results = []
        for hit in search_results:
            combined_text = f"Title: {hit.payload.get('title', '')}. Author: {hit.payload.get('authors', '')}. Summary: {hit.payload.get('short_summary', '')}"
            score = getattr(hit, 'score', 1.0) 
            results.append({
                'text': combined_text, 'title': hit.payload.get('title', ''), 'authors': hit.payload.get('authors', ''),
                'categories': hit.payload.get('categories', ''), 'short_summary': hit.payload.get('short_summary', ''),
                'description': hit.payload.get('description', ''), 'average_rating': hit.payload.get('average_rating', 0.0),
                'thumbnail': hit.payload.get('thumbnail', ''), 'qdrant_score': score 
            })
        return results

    # 🌟 TÍNH NĂNG MỚI: HYBRID SEARCH (TÌM KIẾM LAI KẾT HỢP SONG SONG)
    def hybrid_search(self, user_query, top_k=20, authors=None, categories=None):
        if not user_query or not user_query.strip():
            return self.search_by_idea("", top_k, authors, categories)

        query_filter = self._build_filter(authors, categories)
        results = []
        seen_titles = set()

        # Bước 1: Khớp đích danh Tiêu đề (Exact / Fuzzy Search) -> Đưa lên vị trí đầu tiên
        clean_query = user_query.strip().lower()
        target_title = None
        
        if clean_query in self.exact_title_map:
            target_title = self.exact_title_map[clean_query]
        else:
            # 🌟 ĐÃ SỬA: Dùng fuzz.ratio để tránh lỗi bắt chuỗi con (ngăn chặn "Love" lấn át "I love space discover")
            best_match, score = process.extractOne(user_query, self.all_titles, scorer=fuzz.ratio)
            if score >= 75:  # Ngưỡng tin cậy tìm tên sách
                target_title = best_match

        if target_title:
            matched_rows = self.df_meta[self.df_meta['title'] == target_title]
            if not matched_rows.empty:
                row = matched_rows.iloc[0]
                combined_text = f"Title: {row.get('title', '')}. Author: {row.get('authors', '')}. Summary: {row.get('short_summary', '')}"
                results.append({
                    'text': combined_text, 'title': row.get('title', ''), 'authors': row.get('authors', ''),
                    'categories': row.get('categories', ''), 'short_summary': row.get('short_summary', ''),
                    'description': row.get('description', ''), 'average_rating': float(row.get('average_rating', 0.0)) if pd.notna(row.get('average_rating')) else 0.0,
                    'thumbnail': row.get('thumbnail', ''), 'qdrant_score': 2.0  # Điểm số ưu tiên cao
                })
                seen_titles.add(target_title.lower().strip())

        # Bước 2: Tìm kiếm ngữ nghĩa mở rộng (Vector Embedding) -> Điền vào không gian còn trống
        query_vector = self.model.encode(user_query).tolist()
        search_results = self.qdrant_client.query_points(
            collection_name=self.collection_name, query=query_vector, query_filter=query_filter, limit=top_k + 5
        ).points
        
        for hit in search_results:
            title = hit.payload.get('title', '')
            clean_title = title.lower().strip()
            
            if clean_title in seen_titles:
                continue
                
            seen_titles.add(clean_title)
            combined_text = f"Title: {hit.payload.get('title', '')}. Author: {hit.payload.get('authors', '')}. Summary: {hit.payload.get('short_summary', '')}"
            results.append({
                'text': combined_text, 'title': title, 'authors': hit.payload.get('authors', ''),
                'categories': hit.payload.get('categories', ''), 'short_summary': hit.payload.get('short_summary', ''),
                'description': hit.payload.get('description', ''), 'average_rating': hit.payload.get('average_rating', 0.0),
                'thumbnail': hit.payload.get('thumbnail', ''), 'qdrant_score': hit.score
            })
            if len(results) >= top_k:
                break
                
        return results[:top_k]

    def get_similar_books(self, book_title, top_k=20, authors=None, categories=None):
        if not book_title or not book_title.strip():
            return self.search_by_idea("", top_k, authors, categories)

        clean_query = book_title.strip().lower()
        
        if clean_query in self.exact_title_map:
            target_title = self.exact_title_map[clean_query]
        else:
            best_match, score = process.extractOne(book_title, self.all_titles)
            if score < 60:
                return {"error": f"❌ Không tìm thấy sách nào gần giống với '{book_title}' trong thư viện."}
            target_title = best_match
            
        query_vector = self.model.encode(target_title).tolist()
        query_filter = self._build_filter(authors, categories)
        
        search_results = self.qdrant_client.query_points(
            collection_name=self.collection_name, query=query_vector, query_filter=query_filter, limit=top_k + 3 
        ).points
        
        results = []
        # 🌟 ĐÃ SỬA: Thay thế set chứa sẵn sách gốc bằng set rỗng để lấy lại cuốn sách gốc
        seen_titles = set() 
        
        for hit in search_results:
            title = hit.payload.get('title', '')
            clean_title = title.lower().strip()
            
            if clean_title in seen_titles:
                continue
                
            seen_titles.add(clean_title)
            results.append({
                'title': title, 'authors': hit.payload.get('authors', ''), 'categories': hit.payload.get('categories', ''),
                'short_summary': hit.payload.get('short_summary', ''), 'description': hit.payload.get('description', ''),
                'average_rating': hit.payload.get('average_rating', 0.0), 'thumbnail': hit.payload.get('thumbnail', ''),
                'ai_score': hit.score
            })
            if len(results) >= top_k:
                break
        return results