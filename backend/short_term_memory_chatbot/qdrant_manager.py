from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

def init_memory_collection(qdrant_client):
    collection_name = "chat_memory"
    
    if not qdrant_client.collection_exists(collection_name):
        # 1. Tạo Collection
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        
        # 2. Đánh Index (Mục lục) cho Metadata để tăng tốc độ Search và tránh lỗi 400
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="session_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print(f"✅ Đã tạo collection '{collection_name}' và đánh Index thành công!")