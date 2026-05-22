import os
import pickle
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from transformers import AutoTokenizer
from rank_bm25 import BM25Okapi

def create_qdrant_database():
    def get_root_dir():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.exists(os.path.join(current_dir, "data")):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        raise Exception("❌ Không tìm thấy thư mục 'data'.")

    ROOT_DIR = get_root_dir()
    md_file_path = os.path.join(ROOT_DIR, "data", "pdf_data", "hp_prisoner_full.md")
    qdrant_db_path = os.path.join(ROOT_DIR, "data", "qdrant_db")
    bm25_index_path = os.path.join(ROOT_DIR, "data", "bm25_index.pkl")

    if not os.path.exists(md_file_path):
        print(f"❌ Không tìm thấy file tại: {md_file_path}")
        return

    print("🚀 BẮT ĐẦU TẠO KHO QDRANT...")
    with open(md_file_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # ==========================================
    # CHUNKING
    # ==========================================
    print("✂️ Đang phân tách dữ liệu...")
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = markdown_splitter.split_text(markdown_text)

    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1024,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", "? ", "! ", " "],
        length_function=lambda text: len(tokenizer.encode(text)),
    )
    final_chunks = text_splitter.split_documents(md_header_splits)
    print(f"✅ Đã cắt thành {len(final_chunks)} chunks.")

    # ==========================================
    # LOAD DENSE MODEL
    # ==========================================
    print("🧠 Đang tải Dense Model...")
    dense_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)

    # ==========================================
    # KHỞI TẠO QDRANT
    # ==========================================
    print("🗄️ Đang kết nối Qdrant...")
    client = QdrantClient(path=qdrant_db_path)
    collection_name = "hp_azkaban"

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE),
    )

    # ==========================================
    # EMBED DENSE + UPSERT
    # ==========================================
    texts = [chunk.page_content for chunk in final_chunks]
    texts_to_embed = [f"search_document: {t}" for t in texts]

    print("⏳ Đang tạo Dense Vectors...")
    dense_embeddings = dense_model.encode(texts_to_embed, show_progress_bar=True)

    points = [
        PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload={
                "text": chunk.page_content,
                "source_file": "hp_prisoner_full.pdf",
                **chunk.metadata
            }
        )
        for idx, (chunk, embedding) in enumerate(zip(final_chunks, dense_embeddings))
    ]

    print("⏳ Đang tải lên Qdrant...")
    BATCH_SIZE = 128
    for i in range(0, len(points), BATCH_SIZE):
        client.upsert(collection_name=collection_name, points=points[i:i + BATCH_SIZE])
    print("✅ Đã tải Dense Vectors lên Qdrant.")

    # ==========================================
    # TẠO VÀ LƯU BM25 INDEX
    # ==========================================
    print("⏳ Đang tạo BM25 Index...")
    tokenized_corpus = [text.lower().split() for text in texts]
    bm25 = BM25Okapi(tokenized_corpus)

    with open(bm25_index_path, "wb") as f:
        pickle.dump({"bm25": bm25, "texts": texts}, f)
    print(f"✅ Đã lưu BM25 Index tại: {bm25_index_path}")

    print("\n🎉 HOÀN TẤT! DỮ LIỆU ĐÃ SẴN SÀNG.")

if __name__ == "__main__":
    create_qdrant_database()
