import os
import json
import time
import concurrent.futures
from neo4j import GraphDatabase
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# 1. KHỞI TẠO CÁC KẾT NỐI CLOUD
llm_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_PASSWORD]):
    raise ValueError("❌ Thiếu cấu hình NEO4J_URI hoặc NEO4J_PASSWORD trong file .env!")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

from pdf_ingest import ingest_all_pdfs

# 2. PROMPT TRÍCH XUẤT ĐỒ THỊ (Đã bỏ {text} ở cuối)
GRAPH_EXTRACTION_PROMPT = """You are an expert Knowledge Graph engineer.
Extract named entities and their exact relationships from the text.
Return EXACTLY a valid JSON object with "nodes" and "edges".
- "nodes": [{"id": "Name", "type": "Person/Object/Location"}]
- "edges": [{"source": "id1", "target": "id2", "relation": "UPPERCASE_ACTION"}]
"""

def extract_triplets_from_text(text: str, max_retries=3) -> dict:
    """Gọi LLM qua Groq API, có cơ chế Retry khi bị dính Rate Limit"""
    
    # 🌟 ĐÃ SỬA: Nối chuỗi trực tiếp thay vì dùng .format() để tránh lỗi nhận nhầm {} của JSON
    final_prompt = GRAPH_EXTRACTION_PROMPT + f"\nText Fragment:\n{text}"
    
    for attempt in range(max_retries):
        try:
            res = llm_client.chat.completions.create(
                messages=[{"role": "user", "content": final_prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.1,
                response_format={"type": "json_object"} 
            )
            return json.loads(res.choices[0].message.content)
        
        except RateLimitError:
            wait_time = 5 * (attempt + 1)
            print(f"\n⏳ Quá tải Groq API (Rate Limit)! Đang chờ {wait_time}s trước khi thử lại...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"\n⚠️ Lỗi LLM: {e}")
            return {"nodes": [], "edges": []}
            
    return {"nodes": [], "edges": []}

def push_to_neo4j(tx, graph_data: dict, chunk_id: int, book_name: str):
    """Ghi dữ liệu lên Neo4j"""
    for node in graph_data.get("nodes", []):
        node_id = node.get("id", "").strip()
        node_type = node.get("type", "Entity").strip()
        if node_id:
            tx.run(f"MERGE (n:`{node_type}` {{id: $id}}) ON CREATE SET n.created_at = timestamp()", id=node_id)

    for edge in graph_data.get("edges", []):
        source = edge.get("source", "").strip()
        target = edge.get("target", "").strip()
        relation = edge.get("relation", "RELATED_TO").strip().upper().replace(" ", "_")
        if source and target:
            query = f"""
            MATCH (a {{id: $source}}), (b {{id: $target}})
            MERGE (a)-[r:`{relation}`]->(b)
            SET r.source_chunk = $chunk_id, r.book = $book_name
            """
            tx.run(query, source=source, target=target, chunk_id=chunk_id, book_name=book_name)

def process_single_chunk(chunk: dict, book_name: str):
    """Hàm xử lý độc lập cho 1 luồng (Thread)"""
    chunk_text = chunk["text"]
    chunk_id = chunk["chunk_index"]
    
    # 1. Gọi API (I/O Bound)
    graph_data = extract_triplets_from_text(chunk_text)
    
    # 2. Đẩy lên Neo4j (I/O Bound)
    if graph_data.get("nodes") or graph_data.get("edges"):
        with driver.session() as session:
            session.execute_write(push_to_neo4j, graph_data, chunk_id, book_name)

def build_knowledge_graph_multithread(pdf_folder: str, max_workers: int = 5):
    """Chạy đa luồng để tối đa hóa tốc độ API"""
    all_books = ingest_all_pdfs(pdf_folder, max_tokens=750)
    
    print(f"\n⚡ Bắt đầu trích xuất đồ thị bằng ĐA LUỒNG ({max_workers} luồng đồng thời)...")
    
    for book_name, chunks in all_books.items():
        print(f"\n📖 Đang xử lý: '{book_name}' ({len(chunks)} chunks)")
        
        # Để test, bạn có thể chạy 50 chunks. Chạy thật thì bỏ [:50] đi
        test_chunks = chunks[:50]
        
        # Sử dụng ThreadPoolExecutor để chạy song song
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Tự động map dữ liệu vào các luồng và cập nhật thanh tiến trình
            futures = [executor.submit(process_single_chunk, chunk, book_name) for chunk in test_chunks]
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Graph Extraction"):
                pass
                
    print("\n🎉 HOÀN TẤT!")
    driver.close()

if __name__ == "__main__":
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    pdf_folder = os.path.join(ROOT_DIR, "data", "pdf_data")
    
    # Bắt đầu với 5 luồng. Nếu thấy bị văng lỗi Rate Limit liên tục, hãy hạ xuống 3 hoặc 2
    build_knowledge_graph_multithread(pdf_folder, max_workers=5)