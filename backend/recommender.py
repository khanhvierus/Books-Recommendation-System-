import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os
from thefuzz import process
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
class BookRecommender:
    
    def __init__(self):
        # 1. Định vị đường dẫn động
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        PARENT_DIR = os.path.dirname(CURRENT_DIR)
        
        faiss_path = os.path.join(PARENT_DIR, "data", "books_index_nomic.faiss")
        csv_path = os.path.join(PARENT_DIR, "data", "books_metadata.csv") 
        
        # 2. Nạp dữ liệu
        self.index = faiss.read_index(faiss_path)
        self.df_meta = pd.read_csv(csv_path) 
        
        # 3. KHỞI TẠO MÔ HÌNH EMBEDDING (Dòng bị thiếu)
        # Lưu ý: Hãy thay đổi tên mô hình trong ngoặc kép nếu ban đầu bạn dùng tên khác
        self.model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
   
    # Funtion 1 : Item-to-Item Similarity
    def get_similar_books(self, book_title, top_k=5):
        """
        Chức năng 1: Tìm sách tương tự dựa trên 1 cuốn sách cụ thể (Item-to-Item)
        Đã tích hợp: Truy xuất Vector trực tiếp và Bộ lọc thông minh chống trùng lặp.
        """
        # 1. Tìm cuốn sách trong Metadata để lấy ID
        matched_books = self.df_meta[self.df_meta['title'].str.contains(book_title, case=False, na=False)]
        
        if matched_books.empty:
            return {"error": f"❌ Không tìm thấy sách nào chứa từ khóa '{book_title}'!"}
            
        # Lấy ID (chỉ số dòng) và tên chính xác của cuốn sách khớp đầu tiên
        book_id = matched_books.index[0]
        actual_title = matched_books.iloc[0]['title']
        
        # 2. Rút Vector của chính cuốn sách đó trực tiếp từ FAISS (Tốc độ siêu nhanh)
        book_vector = self.index.reconstruct(int(book_id)) 
        book_vector = np.array([book_vector]).astype('float32')
        
        # 3. Đi tìm hàng xóm gần nhất
        # Mẹo: Lấy dư ra (top_k * 3) để phòng hờ trường hợp lọc bỏ trùng lặp thì vẫn còn đủ sách
        distances, indices = self.index.search(book_vector, top_k * 3)
        
        # Lấy danh sách thô từ Metadata
        similar_books = self.df_meta.iloc[indices[0]].copy()
        similar_books['ai_distance'] = distances[0] # Dùng chung tên ai_distance cho đồng bộ với hàm kia
        
        # ==========================================
        # 4. BỘ LỌC THÔNG MINH (POST-FILTERING)
        # ==========================================
        clean_actual_title = actual_title.lower().strip()
        
        # Lọc 1: Xóa chính cuốn sách gốc ra khỏi kết quả (dựa vào ID)
        filtered_books = similar_books[similar_books.index != book_id]
        
        # Lọc 2: Xóa các cuốn sách là phiên bản khác nhưng có tên trùng khớp 100% với gốc
        filtered_books = filtered_books[filtered_books['title'].str.lower().str.strip() != clean_actual_title]
        
        # Lọc 3: Xóa những cuốn sách trùng tên NHAU trong chính danh sách đang gợi ý
        filtered_books = filtered_books.drop_duplicates(subset=['title'])
        
        # ==========================================
        
        print(f"\n Đang gợi ý các sách tương tự với tâm điểm: '{actual_title}'")
        
        # 5. Cắt lấy đúng số lượng Top K yêu cầu sau khi đã dọn dẹp sạch sẽ
        final_results = filtered_books.head(top_k)
        
        # Trả về dạng Dictionary
        return final_results[['title', 'authors', 'categories', 'average_rating', 'short_summary', 'thumbnail', 'ai_distance']].to_dict(orient='records')
   
    def fuzzy_search_title(self, query, limit=5, threshold=60):
        """Tìm kiếm sách chấp nhận gõ sai chính tả"""
        # Lấy danh sách toàn bộ tên sách
        all_titles = self.df_meta['title'].dropna().tolist()
        
        # Tìm các tên sách giống với query nhất (trả về list các tuple: (tên sách, điểm % giống))
        matches = process.extract(query, all_titles, limit=limit)
        
        results = []
        for match_title, score in matches:
            if score >= threshold: # Chỉ lấy những cuốn giống trên 60%
                # Lấy dữ liệu chi tiết của cuốn sách đó từ df_meta
                book_data = self.df_meta[self.df_meta['title'] == match_title].iloc[0].to_dict()
                book_data['match_score'] = score
                results.append(book_data)
                
        return results
    # Function 2 : Hybrid Search (AI + Rating)
    def hybrid_search(self, user_query, top_k_ai=20, top_k_final=5):
        """
        Chức năng 2 (Nâng cấp toán học): Vector Search + Điểm chuẩn hóa + Rating Boost
        """
        # 1. TÌM KIẾM AI
        query_vector = self.model.encode(["search_query: " + user_query])
        query_vector = np.array(query_vector).astype('float32')
        
        distances, indices = self.index.search(query_vector, top_k_ai)
        
        retrieved_books = self.df_meta.iloc[indices[0]].copy()
        retrieved_books['ai_distance'] = distances[0]
        
        # ==========================================
        # 2. XẾP HẠNG LẠI (RE-RANKING CHUẨN)
        # ==========================================
        # Khoảng cách L2: Càng NHỎ thì càng GIỐNG.
        # Ta chuẩn hóa khoảng cách này về thang điểm từ 0 -> 100
        max_dist = retrieved_books['ai_distance'].max()
        min_dist = retrieved_books['ai_distance'].min()
        
        # Tránh lỗi chia cho 0 nếu tất cả khoảng cách bằng nhau
        if max_dist == min_dist:
            retrieved_books['ai_score'] = 100
        else:
            # Nghịch đảo: Điểm cao nhất (100) cho khoảng cách nhỏ nhất
            retrieved_books['ai_score'] = 100 * (max_dist - retrieved_books['ai_distance']) / (max_dist - min_dist)
        
        # Logic Hybrid: Điểm AI (chiếm 80% sức mạnh) + Điểm Rating (Thưởng tối đa 10 điểm cho sách 5 sao)
        retrieved_books['final_score'] = retrieved_books['ai_score'] + (retrieved_books['average_rating'] * 2)
        
        # 3. LỌC KẾT QUẢ TỐT NHẤT
        final_results = retrieved_books.sort_values(by='final_score', ascending=False).head(top_k_final)
        
        return final_results[['title', 'authors', 'categories', 'short_summary', 'average_rating', 'thumbnail', 'ai_score', 'final_score']].to_dict(orient='records')

# Đoạn code kiểm thử nhanh: Chỉ chạy khi bạn bấm "Run" trực tiếp file này
if __name__ == "__main__":
    recommender = BookRecommender()
    
    print("\n" + "="*50)
    print("BẮT ĐẦU KIỂM THỬ HỆ THỐNG")
    print("="*50)
    
    # ========================================================
    # TEST 1: Tìm kiếm ngữ nghĩa (Chức năng 2 - Text-to-Item)
    # ========================================================
    query = "exploring space" 
    print(f"\n🔍 Đang tìm kiếm với câu hỏi: '{query}'\n")
    
    results = recommender.hybrid_search(query, top_k_final=5)
    
    for i, book in enumerate(results, 1):
        print(f"{i}.  {book['title']} (Tác giả: {book['authors']})")
        # In đúng các cột mà hybrid_search trả về
        print(f"    Thể loại: {book['categories']} |  Độ khớp: {book['ai_score']:.1f}/100 |  Điểm: {book['final_score']:.1f}")
        print("-" * 40)
        
    # ========================================================
    # TEST 2: Gợi ý sách tương tự (Chức năng 1 - Item-to-Item)
    # ========================================================
    book_to_search = "star wars" 
    similar_results = recommender.get_similar_books(book_to_search, top_k=5)
    
    if isinstance(similar_results, dict) and "error" in similar_results:
        print(similar_results["error"])
    else:
        # SỬA LỖI 1: Đã đổi thành similar_results
        for i, book in enumerate(similar_results, 1): 
            print(f"{i}.  {book['title']} (Tác giả: {book['authors']})")
            # SỬA LỖI 2: Đã đổi thành ai_distance cho khớp với hàm get_similar_books
            print(f"    Thể loại: {book['categories']} |  Khoảng cách Vector: {book['ai_distance']:.2f}") 
            print("-" * 40)