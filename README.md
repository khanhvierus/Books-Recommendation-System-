#  RAG Smart Library

A comprehensive Fullstack application that implements **Retrieval-Augmented Generation (RAG)** to provide intelligent book recommendations. The system transitions from traditional keyword searching to semantic "idea-based" discovery using Vector Databases and Large Language Models (LLMs).

---

##  System Architecture: The Dual-Engine Design

The project operates on a strict dual-engine architecture, separating the data-driven search functionality from the conversational AI, while efficiently sharing backend resources (FastAPI & FAISS).

### 1.  Module 1: Search Engine (Discovery Mode)
Triggered via the React sidebar, this module is built for speed and direct book retrieval, returning structured JSON arrays to render book cards.
* **Title Search (Fuzzy Match):** Fast string matching logic to find specific book names while handling minor user typos.
* **Idea Search (Semantic Search):** Converts conceptual user queries (e.g., "books about existential crisis") into mathematical vectors. It scans the shared **FAISS (Facebook AI Similarity Search)** database to retrieve books based on deep meaning rather than exact keywords.

### 2.  Module 2: RAG Chatbot ("AI-Cá Vàng" Consultation)
Triggered via the floating widget, this module acts as a conversational AI expert. It strictly returns sanitized Markdown text.
* **Custom RAG Pipeline:** When a user asks for recommendations, the backend reuses the embedding logic to retrieve relevant book data from FAISS. This data is injected as context into a strict System Prompt for the Groq Cloud API (Llama-3-8B model).
* **Python Gatekeeper:** A logic layer that inspects LLM outputs before they reach the user. 
    * *Security:* It prevents the AI from generating broken image links or hallucinated URLs by stripping unauthorized Markdown tags.
    * *Consistency:* Ensures the AI strictly adheres to the requested quantity of books.
* **Bypass & Latency Simulation:**
    * *Hardcoded Logic:* For specific predefined queries (e.g., project "Easter Eggs" like remembering user data), the system bypasses the LLM entirely to provide 100% accurate, static responses.
    * *Natural UX:* A 1-second artificial delay (`time.sleep(1)`) is implemented for these bypassed responses to mimic a human-like thinking pattern.

### 3.  Frontend Presentation Layer
Built with **React.js**, the frontend focuses on professional minimalism and real-time interaction.
* **Discovery Engine:** A "Curated Discovery" grid automatically fetches 9 random books every 10 seconds via a background interval, ensuring the landing page always feels fresh.
* **Safe Rendering:** Integrated `ReactMarkdown` to parse AI responses safely, with custom component overrides to handle complex formatting, prevent UI-breaking errors, and block hallucinated images.

---

##  Tech Stack

* **Language:** Python 3.x, JavaScript (ES6+)
* **Frameworks:** FastAPI, React.js (Vite)
* **AI/ML:** FAISS, Groq API (Llama-3), Sentence Transformers
* **Security:** Dotenv (.env) for API key management
* **Formatting:** React Markdown, Custom CSS `@keyframes`

---

##  Installation & Setup

1.  **Backend:**
    * Install dependencies: `pip install fastapi uvicorn groq faiss-cpu python-dotenv`
    * Configure `.env` with `GROQ_API_KEY`.
    * Start server: `uvicorn main:app --reload`

2.  **Frontend:**
    * Install dependencies: `npm install`
    * Install Markdown support: `npm install react-markdown`
    * Start development: `npm run dev`

---
##  Video Demo :  **[Drive_Link](https://drive.google.com/file/d/1-qFh57czCc0QnIOQNK_dztiEoabyw7h1/view?usp=sharing)**



## System Block Diagram 

```mermaid
flowchart TD
    %% Styling for visual clarity
    classDef frontend fill:#003366,stroke:#fff,stroke-width:2px,color:#fff;
    classDef api fill:#10b981,stroke:#fff,stroke-width:2px,color:#fff;
    classDef db fill:#f59e0b,stroke:#fff,stroke-width:2px,color:#fff;
    classDef ai fill:#8b5cf6,stroke:#fff,stroke-width:2px,color:#fff;

    User((👤 User)) --> UI[💻 React Frontend]:::frontend

    %% Split flows directly from UI
    UI ===>|1. Search Sidebar| API_S[🔍 API: /search]:::api
    UI ===>|2. Chatbot Widget| API_C[💬 API: /chat]:::api

    %% ==========================================
    %% MODULE 1: SEARCH ENGINE (LEFT SIDE)
    %% ==========================================
    subgraph MODULE 1: SEARCH ENGINE
        API_S --> Mode{Search Mode?}
        Mode -->|By Title| Fuzzy[Fuzzy Match Algorithm]
        Mode -->|By Idea| Embed1[Text to Vector]
        
        Fuzzy --> Data1[(Book Metadata)]:::db
        Embed1 --> FAISS1[(FAISS Vector DB)]:::db
        
        Data1 --> Result1[Return JSON Array]
        FAISS1 --> Result1
    end

    %% ==========================================
    %% MODULE 2: RAG CHATBOT (RIGHT SIDE)
    %% ==========================================
    subgraph MODULE 2: RAG CHATBOT
        API_C --> Filter{Query Type?}
        
        %% VIP Bypass Route
        Filter -->|Special Keyword\ne.g. Ngọc Linh| Bypass[Hardcoded Bypass\n+ 1s Artificial Delay]
        
        %% RAG Route
        Filter -->|General Request| Embed2[Text to Vector]
        Embed2 --> FAISS2[(FAISS Vector DB)]:::db
        FAISS2 --> Prompt[Inject Context to Prompt]
        Prompt --> Llama[[Groq Llama-3 Model]]:::ai
        Llama --> Gate[Python Gatekeeper\nSanitize Format]
        
        Bypass --> Result2[Return Safe Markdown]
        Gate --> Result2
    end

    %% Show shared resource logically without crossing lines
    FAISS1 -.- |"Shared Knowledge Base"| FAISS2

    %% Return to Frontend
    Result1 ===> UI
    Result2 ===> UI
