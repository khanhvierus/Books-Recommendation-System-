import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from dotenv import load_dotenv
load_dotenv()
# ==========================================
# CẤU HÌNH ĐƯỜNG DẪN
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
csv_path = os.path.join(DATA_DIR, "books_metadata_new.csv")
qdrant_path = os.path.join(DATA_DIR, "qdrant_db")

# Tên Collection dành riêng cho Suggest/Recommend
COLLECTION_NAME = "book_metadata_collection"

def ingest_metadata_to_qdrant():
    print("🧠 Đang tải BAAI/bge-m3...")
    model = SentenceTransformer("BAAI/bge-m3")
    vector_size = model.get_embedding_dimension() # 1024

    print("📂 Đang đọc dữ liệu từ books_metadata_new.csv...")
    df = pd.read_csv(csv_path)

    # Dọn dẹp dữ liệu (Thay thế NaN bằng string rỗng để Qdrant không báo lỗi)
    df = df.fillna({
        'title': 'Unknown Title',
        'authors': 'Unknown Author',
        'categories': 'Unknown Category',
        'short_summary': 'No summary available',
        'average_rating': 0.0,
        'thumbnail': 'https://via.placeholder.com/150x220?text=No+Cover'
    })

    # Gộp các trường để tạo văn bản nhúng (Cốt lõi cho Hybrid Search)
    texts = df['title'] + " " + df['authors'] + " " + df['categories'] + " " + df['short_summary']
    texts = texts.tolist()

    print(f"⏳ Đang nhúng {len(texts)} cuốn sách (1024 chiều)...")
    vectors = model.encode(texts, show_progress_bar=True)

    print("💾 Đang kết nối Qdrant...")
    # client = QdrantClient(path=qdrant_path)
    client = QdrantClient(
        url=os.getenv("QDRANT_HOST"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=60
    )

    # Làm sạch Collection cũ nếu có
    if client.collection_exists(collection_name=COLLECTION_NAME):
        print(f"♻️ Xóa collection cũ '{COLLECTION_NAME}'...")
        client.delete_collection(collection_name=COLLECTION_NAME)

    # Khởi tạo Collection bằng Cosine Similarity
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )

    print("🚀 Đang đẩy dữ liệu và Payload vào Qdrant...")
    points = []
    for i, row in df.iterrows():
        payload = {
            "title": row['title'],
            "authors": row['authors'],
            "categories": row['categories'],
            "short_summary": row['short_summary'],
            "average_rating": float(row['average_rating']),
            "thumbnail": row['thumbnail']
        }
        points.append(
            PointStruct(
                id=i,
                vector=np.array(vectors[i], dtype=np.float32).tolist(),
                payload=payload
            )
        )

    # Đẩy lên theo lô (Batch)
    BATCH_SIZE = 128
    for i in range(0, len(points), BATCH_SIZE):
        client.upsert(collection_name=COLLECTION_NAME, points=points[i:i+BATCH_SIZE])

    print(f"✅ HOÀN TẤT! Đã lưu {len(points)} cuốn sách vào Qdrant (Collection: {COLLECTION_NAME}).")

if __name__ == "__main__":
    ingest_metadata_to_qdrant()