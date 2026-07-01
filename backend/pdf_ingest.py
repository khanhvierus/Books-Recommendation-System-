import os
import re
import fitz  # Import PyMuPDF
import nltk
from typing import List, Dict
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Tải gói tách câu của NLTK (Chỉ tải lần đầu)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# ==========================================
# 1. Khởi tạo Tokenizer & Embedding Model
# ==========================================
EMBED_MODEL_NAME = "BAAI/bge-m3"
tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME, use_fast=True)
print("⏳ Đang tải mô hình Embedding cho Semantic Chunking...")
embed_model = SentenceTransformer(EMBED_MODEL_NAME)

# ==========================================
# 2. Parse PDF và normalize text
# ==========================================
def parse_pdf_clean(pdf_path: str) -> str:
    """Đọc PDF bằng PyMuPDF (fitz) để trích xuất văn bản sạch"""
    doc = fitz.open(pdf_path)
    pages = []
    fitz.TOOLS.mupdf_display_errors(False)
    
    for page in doc:
        text = page.get_text()
        if not text:
            continue
            
        text = re.sub(r"-\s*\n\s*", "", text)
        text = text.replace("\n", " ")
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        text = re.sub(r"\s+", " ", text).strip()
        pages.append(text)
        
    return "\n\n".join(pages)

# ==========================================
# 3. Chapter detection
# ==========================================
def split_into_chapters(text: str) -> List[Dict]:
    root_nums = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and"
    word_nums = fr"(?:(?:{root_nums})(?:[\s\-]+(?:{root_nums}))*)"
    
    pattern = re.compile(
        fr'(?i)\bchapter\s+(?:\d+|[ivxlcdm]+|{word_nums})\b'
    )
    
    matches = list(pattern.finditer(text))

    if not matches:
        return [{"chapter_index": 1, "chapter_title": "FULL_BOOK", "text": text}]

    chapters = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapter_text = text[start:end].strip()
        raw_title = m.group(0).strip()
        chapters.append({
            "chapter_index": i + 1,
            "chapter_title": raw_title[:80],
            "text": chapter_text
        })

    return chapters

# ==========================================
# 4. THUẬT TOÁN SEMANTIC CHUNKING
# ==========================================
def semantic_chunk_text(text: str, max_tokens: int = 750, similarity_threshold: float = 0.4) -> List[Dict]:
    """
    Cắt text thành các cụm mang ý nghĩa trọn vẹn (Semantic Boundary).
    - max_tokens: Giới hạn token tối đa cho 1 chunk để LLM dễ "tiêu hóa".
    - similarity_threshold: Mức độ tương đồng Cosine (0->1). Dưới mức này nghĩa là đã sang chủ đề khác.
    """
    # 1. Tách toàn bộ đoạn văn thành các câu riêng biệt
    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return []

    # 2. Vector hóa tất cả các câu trong 1 lần (Tối ưu tốc độ)
    embeddings = embed_model.encode(sentences)

    chunks = []
    current_chunk_sentences = [sentences[0]]
    current_chunk_tokens = len(tokenizer.encode(sentences[0], add_special_tokens=False))
    chunk_index = 0

    for i in range(1, len(sentences)):
        sentence = sentences[i]
        sentence_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))
        
        # 3. Tính độ lệch ngữ nghĩa giữa câu hiện tại (i) và câu trước đó (i-1)
        sim = cosine_similarity([embeddings[i-1]], [embeddings[i]])[0][0]

        # ĐIỀU KIỆN NGẮT CHUNK:
        # Nhảy chủ đề (Similarity < Threshold) HOẶC Chunk đang gom đã quá giới hạn Token
        # ĐIỀU KIỆN NGẮT CHUNK:
        if sim < similarity_threshold or (current_chunk_tokens + sentence_tokens > max_tokens):
            # 1. Lưu chunk hiện tại
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append({
                "chunk_index": chunk_index,
                "text": chunk_text,
                "token_size": current_chunk_tokens
            })
            chunk_index += 1
            
            # 2. KHỞI TẠO CHUNK MỚI VỚI SEMANTIC OVERLAP
            # Mượn lại câu cuối cùng của chunk trước để giữ ngữ cảnh đại từ (He, She, It)
            overlap_sentence = current_chunk_sentences[-1] if current_chunk_sentences else ""
            
            if overlap_sentence:
                current_chunk_sentences = [overlap_sentence, sentence]
                # Tính toán lại token size cho 2 câu này
                overlap_tokens = len(tokenizer.encode(overlap_sentence, add_special_tokens=False))
                current_chunk_tokens = overlap_tokens + sentence_tokens
            else:
                current_chunk_sentences = [sentence]
                current_chunk_tokens = sentence_tokens
        else:
            # Vẫn đang nói cùng chủ đề -> Gộp tiếp vào chunk
            current_chunk_sentences.append(sentence)
            current_chunk_tokens += sentence_tokens

    # Xử lý đoạn text còn sót lại ở cuối cùng
    if current_chunk_sentences:
        chunk_text = " ".join(current_chunk_sentences)
        chunks.append({
            "chunk_index": chunk_index,
            "text": chunk_text,
            "token_size": current_chunk_tokens
        })

    return chunks

# ==========================================
# 5. Ingest all PDFs trong folder
# ==========================================
def ingest_all_pdfs(pdf_folder: str, max_tokens: int = 750) -> Dict[str, List[Dict]]:
    if not os.path.isdir(pdf_folder):
        raise FileNotFoundError(f"PDF folder not found: {pdf_folder}")

    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    all_books = {}

    for pdf in pdf_files:
        book_name = os.path.splitext(pdf)[0]
        pdf_path = os.path.join(pdf_folder, pdf)

        print(f"\n📖 Đang xử lý: {book_name}")
        full_text = parse_pdf_clean(pdf_path)
        chapters = split_into_chapters(full_text)

        chunks_with_metadata = []
        for chap in chapters:
            # GỌI SEMANTIC CHUNKER MỚI
            chapter_chunks = semantic_chunk_text(
                chap["text"], 
                max_tokens=max_tokens, 
                similarity_threshold=0.4  # 0.4 là mức chuẩn tốt cho BGE-M3 (Chủ đề bắt đầu lệch)
            )
            
            for c in chapter_chunks:
                c.update({
                    "chapter_index": chap["chapter_index"],
                    "chapter_title": chap["chapter_title"],
                    "book": book_name
                })
                chunks_with_metadata.append(c)

        print(f"  -> Tổng số Semantic Chunks: {len(chunks_with_metadata)}")
        all_books[book_name] = chunks_with_metadata

    return all_books

# ==========================================
# 6. Test nhanh
# ==========================================
if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    pdf_folder = os.path.join(BASE_DIR, "data", "pdf_data")
    
    books = ingest_all_pdfs(pdf_folder)

    for book, chunks in books.items():
        print(f"\n[{book}] Mẫu chunk đầu tiên (Size: {chunks[0]['token_size']} tokens):")
        print(chunks[0]['text'])
        break