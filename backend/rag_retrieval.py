import json
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from typing import List, Dict

# --- CÁC HÀM XỬ LÝ VECTOR (GIỮ NGUYÊN) ---

def retrieve_top_k(
    query: str,
    qdrant_client: QdrantClient,
    collection_name: str,
    embed_model: SentenceTransformer,
    top_k: int = 20
) -> List[Dict]:
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
    if not retrieved_docs:
        return []
    pairs = [(query, doc["text"]) for doc in retrieved_docs]
    scores = cross_encoder.predict(pairs)
    for doc, score in zip(retrieved_docs, scores):
        doc["cross_score"] = float(score)
    ranked = sorted(retrieved_docs, key=lambda x: x["cross_score"], reverse=True)
    return ranked[:top_k]

# --- CÁC HÀM MỚI: XỬ LÝ GRAPH (NEO4J) ---

def extract_entities(query: str, llm_client) -> List[str]:
    """Dùng LLM siêu tốc để nhặt ra các Danh từ riêng từ câu hỏi"""
    prompt = f"""Extract main named entities (characters, objects, places) from the question to search in a Knowledge Graph.
    Return EXACTLY a JSON object with a single key "entities" containing a list of strings.
    Example: {{"entities": ["Sirius Black", "Firebolt", "Harry Potter"]}}
    Question: {query}"""
    
    try:
        res = llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        return data.get("entities", [])
    except Exception as e:
        print(f"  ⚠️ Lỗi trích xuất Entity: {e}")
        return []

def retrieve_from_graph(entities: List[str], neo4j_driver) -> List[str]:
    """Truy vấn Cypher quét các mối quan hệ xung quanh thực thể"""
    if not entities or not neo4j_driver:
        return []
        
    # Câu lệnh Cypher dùng toLower và CONTAINS để "tìm kiếm mờ" (Fuzzy Search)
    # Ví dụ: "Sirius" vẫn sẽ tìm trúng node "Sirius Black"
    query = """
    UNWIND $entities AS entity
    MATCH (n)-[r]-(m)
    WHERE toLower(n.id) CONTAINS toLower(entity) OR toLower(m.id) CONTAINS toLower(entity)
    RETURN DISTINCT startNode(r).id AS source, type(r) AS relation, endNode(r).id AS target
    LIMIT 50
    """
    graph_context = []
    try:
        with neo4j_driver.session() as session:
            result = session.run(query, entities=entities)
            for record in result:
                src = record["source"]
                rel = record["relation"]
                tgt = record["target"]
                graph_context.append(f"({src}) -[{rel}]-> ({tgt})")
        return graph_context
    except Exception as e:
        print(f"  ⚠️ Lỗi truy vấn Neo4j: {e}")
        return []