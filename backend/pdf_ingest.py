import os
import re
import fitz  # Import PyMuPDF thay cho PyPDF2
from typing import List, Dict
from transformers import AutoTokenizer

# ==========================================
# 1. Tokenizer chuẩn cho embedding model
# ==========================================
# ĐÃ ĐỔI SANG BGE-M3 ĐỂ ĐỒNG BỘ CÁCH ĐẾM TOKEN VỚI QDRANT & DEEP QA
EMBED_MODEL_NAME = "BAAI/bge-m3"
tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME, use_fast=True)

# ==========================================
# 2. Parse PDF và normalize text (Dùng PyMuPDF)
# ==========================================
def parse_pdf_clean(pdf_path: str) -> str:
    """Đọc PDF bằng PyMuPDF (fitz) để trích xuất văn bản sạch, chống lỗi khoảng trắng"""
    doc = fitz.open(pdf_path)
    pages = []
    
    # Tắt cảnh báo màu sắc ICC Profile của PyMuPDF cho console sạch sẽ
    fitz.TOOLS.mupdf_display_errors(False)
    
    for page in doc:
        text = page.get_text()
        if not text:
            continue
            
        # Remove hyphenation at line breaks (gạch nối khi xuống dòng)
        text = re.sub(r"-\s*\n\s*", "", text)
        
        # Flatten newlines to space
        text = text.replace("\n", " ")
        
        # Sửa các lỗi dấu câu bị tách rời (ví dụ: "Dudley ." -> "Dudley.")
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        # Remove multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        
        pages.append(text)
        
    return "\n\n".join(pages)

# ==========================================
# 3. Chapter detection
# ==========================================
def split_into_chapters(text: str) -> List[Dict]:
    """
    Detect chapters tự động bằng Regex tổ hợp gốc từ (Hỗ trợ số vô hạn).
    Trả về list of dict [{'chapter_index': 1, 'chapter_title': 'CHAPTER ONE', 'text': '...'}, ...]
    """
    # 1. Định nghĩa các "viên gạch" cơ bản tạo nên số đếm tiếng Anh
    root_nums = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and"
    
    # 2. Cho phép các viên gạch tự do ghép nối (cách nhau bởi khoảng trắng hoặc gạch ngang)
    # Ví dụ nó sẽ tự bắt được: "twenty-two", "one hundred and one"
    word_nums = fr"(?:(?:{root_nums})(?:[\s\-]+(?:{root_nums}))*)"
    
    # 3. Regex tổng lực: \d+ (bắt số thường) | [ivxlcdm]+ (bắt số La Mã) | word_nums (bắt chữ số tiếng Anh)
    pattern = re.compile(
        fr'(?i)\bchapter\s+(?:\d+|[ivxlcdm]+|{word_nums})\b'
    )
    
    matches = list(pattern.finditer(text))

    if not matches:
        return [{
            "chapter_index": 1,
            "chapter_title": "FULL_BOOK",
            "text": text
        }]

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
# 4. Token-based sliding window chunking
# ==========================================
def chunk_text_tokens(text: str, chunk_size: int = 512, overlap: int = 100) -> List[Dict]:
    """
    Chunk theo token nhưng cắt từ text gốc bằng offset mapping.
    Trả về list of dict [{'chunk_index': 0, 'token_start':..., 'token_end':..., 'text':...}]
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")

    enc = tokenizer(
        text,
        add_special_tokens=False,
        truncation=True,
        max_length=chunk_size,
        stride=overlap,
        return_overflowing_tokens=True,
        return_offsets_mapping=True
    )

    chunks = []
    for i, input_ids in enumerate(enc["input_ids"]):
        offsets = enc["offset_mapping"][i]
        if not offsets:
            continue

        char_start = offsets[0][0]
        char_end = offsets[-1][1]
        chunk_text = text[char_start:char_end].strip()

        if chunk_text:
            chunks.append({
                "chunk_index": i,
                "token_start": i * (chunk_size - overlap),
                "token_end": i * (chunk_size - overlap) + len(input_ids),
                "text": chunk_text
            })

    return chunks

# ==========================================
# 5. Ingest all PDFs trong folder
# ==========================================
def ingest_all_pdfs(pdf_folder: str, chunk_size: int = 512, overlap: int = 100) -> Dict[str, List[Dict]]:
    """
    Trả về dict: {book_name: [chunk1, chunk2, ...]}
    """
    if not os.path.isdir(pdf_folder):
        raise FileNotFoundError(f"PDF folder not found: {pdf_folder}")

    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    all_books = {}

    for pdf in pdf_files:
        book_name = os.path.splitext(pdf)[0]
        pdf_path = os.path.join(pdf_folder, pdf)

        print(f"Đang parse và chunk: {book_name}")
        full_text = parse_pdf_clean(pdf_path)
        chapters = split_into_chapters(full_text)

        chunks_with_metadata = []
        for chap in chapters:
            chapter_chunks = chunk_text_tokens(chap["text"], chunk_size=chunk_size, overlap=overlap)
            for c in chapter_chunks:
                c.update({
                    "chapter_index": chap["chapter_index"],
                    "chapter_title": chap["chapter_title"],
                    "book": book_name
                })
                chunks_with_metadata.append(c)

        print(f"  -> Tổng số chunks: {len(chunks_with_metadata)}")
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
        print(f"{book}: {len(chunks)} chunks")
        print("Sample chunk:", chunks[0])
        break