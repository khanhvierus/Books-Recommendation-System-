import os
import re
import asyncio
import requests
import nest_asyncio
from typing import TypedDict, List
from dotenv import load_dotenv
from groq import Groq
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder
from langgraph.graph import StateGraph, END

from recommender import BookRecommender
from rag_retrieval import retrieve_top_k, rerank_cross_encoder

nest_asyncio.apply()
load_dotenv()

# ==========================================
# 0. KHỞI TẠO CÁC HỆ THỐNG LÕI
# ==========================================
print("🔄 Đang nạp các hệ thống lõi...")

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
ai_system = BookRecommender()  

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
qdrant_db_path = os.path.join(ROOT_DIR, "data", "qdrant_db")

# ĐỒNG BỘ KẾT NỐI QDRANT ĐỂ TRÁNH LỖI PHONG TỎA FILE (FILE LOCKING BUGS)
qdrant_client = ai_system.qdrant_client

print("🧠 Đang tải Cross Encoder...")
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

print("✅ Hệ thống lõi đã sẵn sàng!\n")


# ==========================================
# 1. ĐỊNH NGHĨA TRẠNG THÁI (STATE)
# ==========================================
class AgentState(TypedDict):
    question: str
    intent: str
    context: str
    answer: str
    chat_history: List[dict]


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def get_available_collections() -> List[str]:
    """Lấy danh sách tất cả các bộ sách/tài liệu (ngoại trừ book_metadata_collection)"""
    return [c.name for c in qdrant_client.get_collections().collections if c.name != "book_metadata_collection"]


def generate_multi_queries(question: str, chat_history: List[dict], num_queries: int = 3) -> List[str]:
    """Bẻ câu hỏi phức tạp thành nhiều câu hỏi phụ (sub-queries)."""
    history_text = ""
    if chat_history:
        recent = chat_history[-4:]
        history_text = "\nChat History:\n" + "\n".join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:200]}"
            for m in recent
        ])

    prompt = f"""You are an expert AI search orchestrator. 
Your task is to break down the user's complex question into {num_queries} distinct, highly specific search queries to query a vector database.

Strategy:
1. Resolve any pronouns to full character names.
2. Create angles that cover the whole "Multi-hop" reasoning path (e.g., identity, motive, action, event).
3. Ensure synonyms are used if helpful.

{history_text}
Original Question: {question}

Provide EXACTLY {num_queries} queries. Output ONLY the queries, one per line. Do NOT use bullet points, numbers, or introductory text."""

    try:
        res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=150
        )
        content = res.choices[0].message.content.strip()
        
        raw_queries = content.split('\n')
        clean_queries = [re.sub(r'^[\d\-\.\*]+\s*', '', q).strip() for q in raw_queries if q.strip()]
        final_queries = list(set([question] + clean_queries))
        
        print("\n  🔄 [MULTI-QUERY DECOMPOSITION]")
        for i, q in enumerate(final_queries):
            print(f"    Q{i+1}: {q}")
            
        return final_queries
    except Exception as e:
        print(f"  ⚠️ Lỗi tạo Multi-query: {e}")
        return [question]


def web_search_tavily(query: str, api_key: str, top_k: int = 3) -> List[str]:
    """Tìm kiếm web bằng Tavily API (POST request)"""
    endpoint = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": top_k,
        "search_depth": "basic",
        "include_answer": False
    }
    response = requests.post(endpoint, json=payload)
    response.raise_for_status()
    data = response.json()
    snippets = []
    for result in data.get("results", []):
        snippet = result.get("content", "")
        url = result.get("url", "")
        snippets.append(f"{snippet}\n(Source: {url})")
    return snippets


# ==========================================
# 3. XÂY DỰNG CÁC TRẠM (NODES)
# ==========================================

async def router_node(state: AgentState) -> AgentState:
    sys_prompt = """You are a Router Agent. Classify the user's message into EXACTLY ONE category:
- 'ROUTE_GENERAL': Greetings, chit-chat, general questions, or user wants to discover/find new books.
- 'ROUTE_DEEP_QA': User asks about plot, characters, events, or reasons IN a specific book.
Output ONLY the category name."""

    res = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": state["question"]}
        ],
        model="llama-3.1-8b-instant",
        temperature=0,
        max_tokens=20
    )
    return {"intent": res.choices[0].message.content.strip()}


async def general_node(state: AgentState) -> AgentState:
    print("-> 🟢📚 Trạm GIAO TIẾP & TƯ VẤN SÁCH CHUNG")
    
    match = re.search(r'(\d+)', state["question"])
    fetch_count = min(max(int(match.group(1)), 3), 10) if match else 3

    # GIAI ĐOẠN 1: Retrieval
    retrieved_books = []
    if len(state["question"].strip()) > 10:
        retrieved_books = ai_system.search_by_idea(state["question"], top_k=15)

    # GIAI ĐOẠN 2: Re-rank
    reranked_books = []
    if retrieved_books:
        print(f"  🔍 Đang Re-rank {len(retrieved_books)} cuốn sách tiềm năng...")
        reranked_books = rerank_cross_encoder(
            query=state["question"],
            retrieved_docs=retrieved_books,
            cross_encoder=cross_encoder,
            top_k=fetch_count
        )

    # GIAI ĐOẠN 3: Build Context & LLM Generation
    context_text = "\n".join([
        f"- {b['title']} (Author: {b.get('authors', '')}) - Summary: {b.get('short_summary', '')}"
        for b in reranked_books
    ])

    sys_prompt = f"""You are AI-Goldfish, a friendly and warm library assistant. Reply in ENGLISH.
- If the user is greeting or chit-chatting, answer warmly in English.
- If the user is asking for book recommendations, recommend books based STRICTLY on this context:
{context_text}

FORMAT for each recommended book:
**[Title]**
- **Author:** [Author]  
- **Summary:** [Summary]"""

    # --- ĐÃ SỬA CHỮA: Nạp lịch sử vào Messages ---
    messages = [{"role": "system", "content": sys_prompt}]
    for msg in state.get("chat_history", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": state["question"]})

    res = groq_client.chat.completions.create(
        messages=messages,
        model="llama-3.1-8b-instant"
    )
    answer = res.choices[0].message.content.strip()
    
    history = state.get("chat_history", []) + [
        {"role": "user", "content": state["question"]},
        {"role": "assistant", "content": answer}
    ]
    return {"context": context_text, "answer": answer, "chat_history": history}


async def deep_qa_node(state: AgentState) -> AgentState:
    print("-> 🧙 Trạm HỌC THUẬT (GLOBAL SEARCH)")
    print("  Pipeline: Multi-Query → Global Pool Retrieval → Deduplication → Re-rank → Web Fallback → Generation")

    question = state["question"]
    chat_history = state.get("chat_history", [])

    available_collections = get_available_collections()
    if not available_collections:
        return {"answer": "No book data available. Please run embed_to_qdrant.py first."}

    queries = generate_multi_queries(question, chat_history)

    # BƯỚC 1: GLOBAL RETRIEVAL
    all_retrieved_docs = []
    seen_chunk_ids = set()

    print(f"  ⏳ Đang quét Vector DB trên {len(available_collections)} cuốn sách cho tất cả sub-queries...")
    for q in queries:
        for collection in available_collections:
            docs = retrieve_top_k(
                query=q,
                qdrant_client=qdrant_client,
                collection_name=collection,
                embed_model=ai_system.model,
                top_k= 50  
            )
            
            for doc in docs:
                chunk_id = f"{collection}_{doc.get('metadata', {}).get('chunk_id', doc['text'])}"
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_retrieved_docs.append(doc)
                
    print(f"  📥 Tổng số chunks độc nhất gom được từ toàn bộ thư viện: {len(all_retrieved_docs)}")

    # BƯỚC 2: RE-RANK TOÀN BỘ BỂ DỮ LIỆU
    reranked_docs = rerank_cross_encoder(
        query=question, 
        retrieved_docs=all_retrieved_docs,
        cross_encoder=cross_encoder,
        top_k=10
    )

    # BƯỚC 3: XỬ LÝ CONTEXT + WEB SEARCH FALLBACK
    context_parts = []
    best_score = reranked_docs[0]["cross_score"] if reranked_docs else -999

    if not reranked_docs or best_score < 0.1:
        print(f"  🌐 Điểm DB cao nhất ({best_score:.4f}) hơi thấp, kích hoạt Web Search...")
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if tavily_key:
            try:
                web_results = web_search_tavily(question, tavily_key, top_k=3)
                if web_results:
                    context_parts.append("[DATA FROM WEB SEARCH]")
                    for i, snip in enumerate(web_results):
                        context_parts.append(f"Web Snippet {i+1}:\n{snip}")
            except Exception as e:
                print(f"  ⚠️ Web Search Error: {e}")

    if reranked_docs:
        print("\n--- 🔍 [TOP 10 CHUNKS TỪ TOÀN BỘ THƯ VIỆN SAU RE-RANK] ---")
        context_parts.append("[DATA FROM BOOKS (QDRANT)]")
        for i, doc in enumerate(reranked_docs):
            score = doc["cross_score"]
            meta = doc.get("metadata", {})
            book_name = meta.get("book", "Unknown Book")
            chapter = meta.get("chapter_title", "Unknown Chapter")
            text = doc.get("text", "")
            
            print(f"  [{book_name} | {chapter}] Score = {score:.4f}")
            context_parts.append(f"--- Source: {book_name} - {chapter} ---\n{text}")
        print("------------------------------------\n")

    context_text = "\n\n".join(context_parts)

    if not context_text.strip():
        return {"answer": "There is not enough information currently available to answer this question."}

    # BƯỚC 4: GENERATION (ÉP TRÍCH DẪN & TIẾNG ANH & CHAIN-OF-THOUGHT)
    print("\n--- 🕵️‍♂️ [DEBUG] CONTEXT ĐƯA VÀO LLM ---")
    print(context_text[:1500] + "...\n(Đã rút gọn để hiển thị)") 
    print("---------------------------------------\n")

    sys_prompt = f"""You are an expert book assistant. Answer the user's question using ONLY the context provided below.

Rules:
1. Reply entirely in ENGLISH.
2. Synthesize the context pieces logically to provide a detailed, accurate answer.
3. CRITICAL: You MUST cite the source book and chapter if the information comes from the books (e.g., "According to [Book Name] - [Chapter Name], Sirius...").
4. If the context does NOT contain enough information: say "There is not enough information currently available to answer this question."
5. Do NOT hallucinate or make up any information outside the provided context.

INSTRUCTIONS FOR REASONING (Chain-of-Thought):
Before answering, you MUST think step-by-step. Enclose your thought process within <thinking> tags.
1. Identify the core entities and constraints in the user's question.
2. Scan the provided Context for evidence related to these entities.
3. Verify if the evidence fully answers the question. If information is missing, explicitly state it within your thoughts.
4. Formulate a concise, accurate answer based ONLY on the verified evidence.

FORMAT:
<thinking>
[Your step-by-step reasoning here]
</thinking>
Final Answer: [Your actual response to the user]

CONTEXT:
{context_text}"""

    # --- ĐÃ SỬA CHỮA: Nạp lịch sử vào Messages ---
    messages = [{"role": "system", "content": sys_prompt}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    res = groq_client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    
    raw_answer = res.choices[0].message.content.strip()
    
    # Phân tách để lưu câu trả lời sạch vào Chat History
    answer_to_display = raw_answer
    if "<thinking>" in raw_answer and "Final Answer:" in raw_answer:
        answer_to_display = raw_answer.split("Final Answer:")[-1].strip()

    history = chat_history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer_to_display}
    ]
    return {"context": context_text, "answer": raw_answer, "chat_history": history}


# ==========================================
# 4. LẮP RÁP ĐỒ THỊ LANGGRAPH
# ==========================================
def route_direction(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "ROUTE_DEEP_QA": return "deep_qa"
    else: return "general"

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("general", general_node)
workflow.add_node("deep_qa", deep_qa_node)

workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router",
    route_direction,
    {"deep_qa": "deep_qa", "general": "general"}
)
workflow.add_edge("general", END)
workflow.add_edge("deep_qa", END)

app_graph = workflow.compile()


# ==========================================
# 5. CHAT LOOP
# ==========================================
async def chat_loop():
    print("🤖 SMART LIBRARY AI ĐÃ KHỞI ĐỘNG! (Gõ 'quit' để thoát)\n" + "-"*50)
    chat_history = []

    while True:
        user_input = input("\n👤 Bạn: ")
        if user_input.lower() in ["quit", "exit"]:
            break

        initial_state = {
            "question": user_input,
            "intent": "",
            "context": "",
            "answer": "",
            "chat_history": chat_history
        }

        final_state = await app_graph.ainvoke(initial_state)
        chat_history = final_state.get("chat_history", [])

        print(f"\n🤖 AI-CÁ VÀNG:\n{final_state['answer']}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(chat_loop())