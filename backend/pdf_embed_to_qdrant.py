import os
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from pdf_ingest import ingest_all_pdfs
from dotenv import load_dotenv

load_dotenv()

def embed_and_store_to_qdrant(
    pdf_folder: str,
    qdrant_path: str,
    model_name: str = "BAAI/bge-m3" # ĐÃ ĐỔI SANG MÔ HÌNH MỚI
):
    """
    Parse tất cả PDF trong pdf_folder thành list các dict (chứa metadata)
    → Embed phần 'text' bằng BGE-M3 → Lưu toàn bộ vào Qdrant.
    Mỗi cuốn sách = 1 collection riêng.
    """
    # 1. Load embedding model
    print("🧠 Đang tải Embedding Model (BAAI/bge-m3)...")
    model = SentenceTransformer(model_name)
    vector_size = model.get_embedding_dimension() # Sẽ tự động lấy giá trị 1024

    # 2. Parse tất cả PDF thành chunks bằng Semantic Chunking
    print("📂 Đang băm nhỏ file PDF (Semantic Chunking)...")
    
    # 🌟 ĐÃ SỬA XUNG ĐỘT: Gọi đúng tham số max_tokens của hàm mới
    all_books = ingest_all_pdfs(pdf_folder, max_tokens=500)
    
    if not all_books:
        print("❌ Không tìm thấy file PDF nào trong folder!")
        return

    # 3. Kết nối Qdrant Cloud
    client = QdrantClient(
        url=os.getenv("QDRANT_HOST"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=60
    )
    existing_collections = [c.name for c in client.get_collections().collections]

    for book_name, chunks in all_books.items():
        print(f"\n📚 Đang xử lý: '{book_name}' ({len(chunks)} chunks)")

        # Xóa collection cũ (đang chứa vector 768 chiều) để dọn đường
        if book_name in existing_collections:
            print(f"  ♻️  Xóa collection cũ '{book_name}'...")
            client.delete_collection(book_name)

        # Tạo collection mới (chuẩn bị đón vector 1024 chiều)
        client.create_collection(
            collection_name=book_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )

        # 4. Embed chunks
        print(f"  ⏳ Đang chuyển đổi văn bản thành Vector 1024 chiều...")
        texts_to_embed = [chunk['text'] for chunk in chunks]
        vectors = model.encode(texts_to_embed, show_progress_bar=True)

        # 5. Upsert vào Qdrant theo batch
        BATCH_SIZE = 128
        points = []
        
        for i, (vec, chunk_dict) in enumerate(zip(vectors, chunks)):
            # 🌟 ĐÃ SỬA: Cập nhật Payload để khớp với metadata của Semantic Chunking
            payload = {
                "text": chunk_dict["text"],
                "book": chunk_dict["book"],
                "chapter_title": chunk_dict.get("chapter_title", "Unknown"),
                "chapter_index": chunk_dict.get("chapter_index", 0),
                "chunk_id": chunk_dict["chunk_index"],
                "token_size": chunk_dict.get("token_size", 0) # Ghi nhận độ lớn thực tế của chunk
            }
            
            points.append(
                PointStruct(
                    id=i,
                    vector=np.array(vec, dtype=np.float32).tolist(),
                    payload=payload
                )
            )

        # Ghi vào Qdrant
        for i in range(0, len(points), BATCH_SIZE):
            client.upsert(collection_name=book_name, points=points[i:i + BATCH_SIZE])

        print(f"  ✅ Đã lưu {len(points)} chunks vào collection '{book_name}'")

    print("\n🎉 HOÀN TẤT! Tất cả sách đã được index vào Qdrant với Siêu dữ liệu đầy đủ.")
    print("Các Collections hiện có trong Database (bao gồm cả metadata):")
    for c in client.get_collections().collections:
        print(f"  - {c.name}")

if __name__ == "__main__":
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    pdf_folder = os.path.join(ROOT_DIR, "data", "pdf_data")
    qdrant_path = os.path.join(ROOT_DIR, "data", "qdrant_db")
    
    embed_and_store_to_qdrant(pdf_folder, qdrant_path)