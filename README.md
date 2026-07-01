# Smart Library
---
##  Key Features
### 1. Enterprise-Grade Security
* **JWT Authentication:** Secure user registration and login workflows.
* **Role-Based Memory Isolation:** User chat histories are strictly isolated using PostgreSQL IDs and Redis session keys.
### 2. Advanced Discovery & Search
* **Fuzzy Match (By Title):** Instantly finds book titles despite typos using `thefuzz`.
* **Semantic Vector Search (By Idea):** Users can describe a plot, mood, or idea. The system uses **SentenceTransformers (BAAI/bge-m3)** to search millions of vector dimensions in **Qdrant** to find the most conceptually similar books.
* **Curated UI Layout:** A minimalist, highly responsive React layout that dynamically adjusts between 2x2 grids and vertical lists.
### 3. The Multi-Agent Chatbot
* **Agentic Routing:** Utilizes **LangGraph** to classify user intent (Chit-chat vs. Deep Academic QA).
* **Short-Term Memory:** Real-time conversation tracking powered by **Redis Cloud**.
* **Deep QA Pipeline:** Bypasses basic searches by using LLM to break down complex queries into sub-queries, retrieving chunks from Qdrant, deduplicating, and synthesizing answers via Chain-of-Thought (CoT).
* **Web Search Fallback:** Automatically queries the live web via **Tavily API** if the internal Vector DB lacks sufficient context.
* **Cross-Encoder Re-ranking:** Re-scores retrieved context using `ms-marco-MiniLM-L-6-v2` to ensure only the highest quality data reaches the LLM.
---
## Tech Stack & Methodologies
| Category | Tools & Technologies |
| :--- | :--- |
| **Frontend** | React 19, Vite, CSS-in-JS (Minimalist Design), React-Markdown |
| **Backend** | Python, FastAPI, SQLAlchemy, Uvicorn |
| **Databases** | PostgreSQL (User Auth), Redis Cloud Upstash (Memory), Qdrant (Vector DB) |
| **AI / LLM** | LangGraph, Llama-3 / Llama-3.3 (via Groq API) |
| **NLP & RAG** | SentenceTransformers (`BAAI/bge-m3`), Cross-Encoder, Tavily Web Search |
| **Data Processing** | Pandas, TheFuzz |
---
## System Architecture

### Diagram 1 — System Overview

Toàn cảnh các thành phần và luồng dữ liệu chính giữa Frontend, Backend, Storage và AI Agent.

![System Architecture Overview](./docs/architecture-overview.svg)

---

### Diagram 2 — Chatbot Deep Dive: Multi-Agent RAG Pipeline

Chi tiết luồng xử lý bên trong AI Agent qua 3 trạm kiểm soát:

- **Trạm 1 — Router Node**: Phân loại ý định người dùng. Nếu là chào hỏi hoặc tư vấn sách chung → Trạm 2. Nếu là câu hỏi học thuật phức tạp → Trạm 3.
- **Trạm 2 — General Node**: Tìm vài cuốn sách tiềm năng trong Qdrant, tóm tắt và đưa vào LLM để trả lời thân thiện, ấm áp.
- **Trạm 3 — Deep QA Node**: Kích hoạt pipeline RAG 5 bước — phân thân sub-queries → global retrieval (50 chunks) → cross-encoder re-ranking (top 10) → Tavily web fallback nếu điểm thấp → Chain-of-Thought synthesis với trích dẫn nguồn.

![RAG Pipeline Deep Dive](./docs/rag-pipeline.svg)
---

## 🎬 Demo

Watch the full system walkthrough — search, authentication, and chatbot RAG pipeline in action:

▶️ **[Watch Demo on Google Drive](https://drive.google.com/file/d/1WmlV0TjUiP1a_0ELabJVkzb7VUWbwWP5/view?usp=sharing)**

---

## 📊 RAG Evaluation — RAGAS Report

The chatbot's Deep QA pipeline was evaluated using the **[RAGAS](https://docs.ragas.io/)** framework across **15 test cases** covering chit-chat, book recommendations, and factual Q&A over the Harry Potter corpus.

### Metric Results

| Metric | Description | Score |
| :--- | :--- | :---: |
| **Context Precision** | Are retrieved chunks relevant to the question? | 0.667 |
| **Context Recall** | Does the retrieved context cover the reference answer? | 0.600 |
| **Faithfulness** | Is the generated answer grounded in retrieved context (no hallucination)? | 0.500 |
| **Answer Relevancy** | Is the answer on-topic and directly addressing the user's question? | 0.879 |

> Scores range from 0.0 (worst) to 1.0 (best). Metrics with fewer valid samples reflect cases where the pipeline routed to General (chit-chat) node and no retrieval was performed.

### Key Observations

- **Answer Relevancy (0.879)** is the strongest metric — the chatbot consistently stays on-topic and gives coherent, relevant responses.
- **Faithfulness (0.500)** indicates room for improvement in grounding answers strictly within retrieved context, particularly for ambiguous or cross-book queries.
- **Context Recall (0.600)** suggests the vector search occasionally misses relevant passages — a candidate for tuning chunk size or retrieval `top-K`.
- **Context Precision (0.667)** shows that when context is retrieved, most chunks are relevant, but some noise remains before re-ranking.

> Full per-sample breakdown is available in [`ragas_report.csv`](./ragas_report.csv).
