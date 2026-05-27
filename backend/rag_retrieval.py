from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from typing import List, Dict

def retrieve_top_k(
    query: str,
    qdrant_client: QdrantClient,
    collection_name: str,
    embed_model: SentenceTransformer,
    top_k: int = 20
) -> List[Dict]:
    """
    Bước 1+2: Query Embedding + Retrieval
    Trả về danh sách các dictionary chứa đầy đủ text, metadata và score từ Qdrant.
    """
    # ĐÃ SỬA: Xóa bỏ chữ f"search_query: " vì BGE-M3 không cần đến nó
    query_vec = embed_model.encode(query).tolist()

    response = qdrant_client.query_points(
        collection_name=collection_name,
        query=query_vec,
        limit=top_k
    )
    
    return [
        {
            "text": hit.payload["text"],
            "metadata": hit.payload,
            "qdrant_score": hit.score
        }
        for hit in response.points
    ]

def rerank_cross_encoder(
    query: str,
    retrieved_docs: List[Dict],
    cross_encoder: CrossEncoder,
    top_k: int = 5
) -> List[Dict]:
    """
    Bước 3: Re-rank
    Chấm điểm lại bằng Cross Encoder nhưng vẫn giữ nguyên vẹn Metadata.
    """
    if not retrieved_docs:
        return []

    # Rút text ra để chấm điểm
    pairs = [(query, doc["text"]) for doc in retrieved_docs]
    scores = cross_encoder.predict(pairs)
    
    # Gắn điểm mới vào từng document
    for doc, score in zip(retrieved_docs, scores):
        doc["cross_score"] = float(score)
        
    # Sắp xếp lại dựa trên điểm Cross-Encoder (từ cao xuống thấp)
    ranked = sorted(retrieved_docs, key=lambda x: x["cross_score"], reverse=True)
    return ranked[:top_k]