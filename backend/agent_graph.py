import os
import re
import pickle
import asyncio
import nest_asyncio
from typing import TypedDict, List
from dotenv import load_dotenv
from groq import Groq
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

# Thư viện LangGraph
from langgraph.graph import StateGraph, END

# Import class FAISS
from recommender import BookRecommender

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

# Khởi tạo Qdrant
qdrant_client = QdrantClient(path=qdrant_db_path)
QDRANT_COLLECTION = "hp_azkaban"

# Load BM25 Index
bm25_index_path = os.path.join(ROOT_DIR, "data", "bm25_index.pkl")
with open(bm25_index_path, "rb") as f:
    bm25_data = pickle.load(f)
bm25 = bm25_data["bm25"]
bm25_texts = bm25_data["texts"]

print("✅ Hệ thống lõi đã sẵn sàng!\n")

# ==========================================
# 1. ĐỊNH NGHĨA TRẠNG THÁI (STATE)
# ==========================================
class AgentState(TypedDict):
    question: str
    intent: str
    context: str
    answer: str
    chat_history: List[dict]  # Lưu lịch sử hội thoại cho Reflection

# ==========================================
# 2. HÀM REFLECTION — Reformulate câu hỏi
# ==========================================
def reflection(question: str, chat_history: List[dict]) -> str:
    """
    Dùng LLM reformulate câu hỏi thành 1 câu độc lập, đầy đủ ngữ cảnh.
    Ví dụ:
      History: "Sirius là ai?"
      Question: "Tại sao ông ấy tặng cây chổi?"
      Reflected: "Tại sao Sirius Black tặng Harry Potter cây chổi Firebolt?"
    """
    if not chat_history:
        history_text = "No previous conversation."
    else:
        # Lấy tối đa 4 lượt hội thoại gần nhất
        recent = chat_history[-4:]
        history_text = "\n".join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in recent
        ])

    res = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """You are a query reformulation expert for a book Q&A system about "Harry Potter and the Prisoner of Azkaban".

Given a chat history and the latest user question, reformulate the question into a clear, standalone search query that:
1. Includes full names of characters/objects (e.g., "Sirius Black" not "he", "Firebolt broomstick" not "it")
2. Uses diverse vocabulary to maximize search recall (e.g., include synonyms like "gave/sent/gifted")
3. Is self-contained — can be understood WITHOUT the chat history
4. Preserves the original intent of the question

Output ONLY the reformulated query. No explanation, no preamble."""
            },
            {
                "role": "user",
                "content": f"Chat History:\n{history_text}\n\nLatest Question: {question}"
            }
        ],
        model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=100
    )

    reflected = res.choices[0].message.content.strip()
    print(f"  🔄 Reflection: '{question}'\n             → '{reflected}'")
    return reflected


# ==========================================
# 3. XÂY DỰNG CÁC TRẠM (NODES)
# ==========================================

async def router_node(state: AgentState) -> AgentState:
    sys_prompt = """You are a Router Agent. Classify the user's message into EXACTLY ONE category:
    - 'ROUTE_RECOMMEND': User wants to find or discover new books.
      Examples: "gợi ý sách hay", "tìm sách về phép thuật", "recommend me a book"
    - 'ROUTE_DEEP_QA': User asks about plot, characters, or events IN a specific book.
      Examples: "Why did Sirius give Harry the Firebolt?", "Who is the Half-Blood Prince?"
    - 'ROUTE_CHAT': Greetings or general chit-chat.
      Examples: "xin chào", "cảm ơn bạn", "hello"
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


async def chat_node(state: AgentState) -> AgentState:
    print("-> 🟢 Chạy vào Trạm CHAT")
    res = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are AI-CÁ VÀNG, a friendly library assistant. Reply warmly in VIETNAMESE."},
            {"role": "user", "content": state["question"]}
        ],
        model="llama-3.1-8b-instant"
    )
    answer = res.choices[0].message.content.strip()
    updated_history = state.get("chat_history", []) + [
        {"role": "user", "content": state["question"]},
        {"role": "assistant", "content": answer}
    ]
    return {"answer": answer, "chat_history": updated_history}


async def recommend_node(state: AgentState) -> AgentState:
    print("-> 📚 Chạy vào Trạm TƯ VẤN SÁCH (FAISS)")
    match = re.search(r'(\d+)', state["question"])
    fetch_count = min(max(int(match.group(1)), 3), 10) if match else 3

    books = ai_system.hybrid_search(state["question"])[:fetch_count]
    context_text = "\n".join([
        f"- {b['title']} (Tác giả: {b.get('authors', '')}) - Tóm tắt: {b.get('short_summary', '')}"
        for b in books if isinstance(b, dict)
    ])

    sys_prompt = f"""You are AI-CÁ VÀNG. Recommend books based strictly on this context:
    {context_text}
    FORMAT:
    **[Title]**
    - **Author:** [Author]
    - **Summary:** [Summary]
    Reply in VIETNAMESE."""

    res = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": state["question"]}
        ],
        model="llama-3.1-8b-instant"
    )
    answer = res.choices[0].message.content.strip()
    updated_history = state.get("chat_history", []) + [
        {"role": "user", "content": state["question"]},
        {"role": "assistant", "content": answer}
    ]
    return {"context": context_text, "answer": answer, "chat_history": updated_history}


async def deep_qa_node(state: AgentState) -> AgentState:
    print("-> 🧙‍♂️ Chạy vào Trạm HỌC THUẬT (HYBRID + REFLECTION)")

    question = state["question"]
    chat_history = state.get("chat_history", [])

    # ==========================================
    # BƯỚC 1: REFLECTION — Reformulate câu hỏi
    # ==========================================
    reflected_query = reflection(question, chat_history)

    # ==========================================
    # BƯỚC 2: HYBRID SEARCH với reflected query
    # ==========================================

    # --- DENSE SEARCH ---
    dense_vec = ai_system.model.encode(
        f"search_query: {reflected_query}"
    ).tolist()

    dense_response = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=dense_vec,
        limit=20,
    )
    dense_scores = {hit.id: hit.score for hit in dense_response.points}

    # --- BM25 SEARCH ---
    tokenized_query = reflected_query.lower().split()
    bm25_scores_raw = bm25.get_scores(tokenized_query)
    top_bm25_ids = sorted(
        range(len(bm25_scores_raw)),
        key=lambda i: bm25_scores_raw[i],
        reverse=True
    )[:20]
    bm25_scores = {idx: float(bm25_scores_raw[idx]) for idx in top_bm25_ids}

    # --- RRF FUSION ---
    K = 60
    rrf_scores = {}
    for rank, doc_id in enumerate(sorted(dense_scores, key=dense_scores.get, reverse=True)):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (K + rank + 1)
    for rank, doc_id in enumerate(sorted(bm25_scores, key=bm25_scores.get, reverse=True)):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (K + rank + 1)

    top_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:8]

    # --- LẤY TEXT THEO ID ---
    all_qdrant_payloads = {hit.id: hit.payload["text"] for hit in dense_response.points}

    context_parts = []
    print("\n--- 🔍 [HYBRID SEARCH RESULTS] ---")
    for i, doc_id in enumerate(top_ids):
        text = all_qdrant_payloads.get(doc_id) or bm25_texts[doc_id]
        tag = "🔥" if "firebolt" in text.lower() else ""
        has_reason = "✅" if any(kw in text.lower() for kw in ["because", "godfather", "sent you", "thirteen birthdays"]) else ""
        print(f"  [Đoạn {i+1}] id={doc_id} RRF={rrf_scores[doc_id]:.4f} {tag}{has_reason}")
        context_parts.append(f"[Đoạn {i+1}]\n{text}")
    print("-----------------------------------\n")

    if not context_parts:
        return {"answer": "Tôi không tìm thấy thông tin liên quan trong sách."}

    context_text = "\n\n---\n\n".join(context_parts)

    # ==========================================
    # BƯỚC 3: LLM TRẢ LỜI
    # ==========================================
    sys_prompt = f"""You are an expert on "Harry Potter and the Prisoner of Azkaban".
Answer the user's question using ONLY the context provided below.

Rules:
- Reply in VIETNAMESE.
- If the context contains the answer, give a detailed and complete answer.
- If the context does not contain enough information, say: "Thông tin trong sách không đủ để trả lời câu hỏi này."
- Do NOT make up information.
- Be specific — reference character names and events from the context.

CONTEXT:
{context_text}"""

    res = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question}
        ],
        model="llama-3.1-8b-instant",
        temperature=0.2
    )
    answer = res.choices[0].message.content.strip()

    # Cập nhật chat history
    updated_history = chat_history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer}
    ]

    return {
        "context": context_text,
        "answer": answer,
        "chat_history": updated_history
    }


# ==========================================
# 4. LẮP RÁP ĐỒ THỊ
# ==========================================
def route_direction(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "ROUTE_DEEP_QA": return "deep_qa"
    elif intent == "ROUTE_RECOMMEND": return "recommend"
    else: return "chat"

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("chat", chat_node)
workflow.add_node("recommend", recommend_node)
workflow.add_node("deep_qa", deep_qa_node)

workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router",
    route_direction,
    {"deep_qa": "deep_qa", "recommend": "recommend", "chat": "chat"}
)
workflow.add_edge("chat", END)
workflow.add_edge("recommend", END)
workflow.add_edge("deep_qa", END)

app_graph = workflow.compile()

# ==========================================
# 5. CHAT LOOP
# ==========================================
async def chat_loop():
    print("🤖 HỆ THỐNG LANGGRAPH ĐÃ KHỞI ĐỘNG! (Gõ 'quit' để thoát)\n" + "-"*50)

    # Duy trì chat history xuyên suốt session
    chat_history = []

    while True:
        user_input = input("\n👤 Bạn: ")
        if user_input.lower() in ['quit', 'exit']:
            break

        initial_state = {
            "question": user_input,
            "intent": "",
            "context": "",
            "answer": "",
            "chat_history": chat_history
        }

        final_state = await app_graph.ainvoke(initial_state)

        # Cập nhật chat history cho lượt tiếp theo
        chat_history = final_state.get("chat_history", [])

        print(f"\n🤖 AI-CÁ VÀNG:\n{final_state['answer']}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(chat_loop())
