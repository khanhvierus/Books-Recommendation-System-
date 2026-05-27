import sys
from unittest.mock import MagicMock
sys.modules['langchain_community.chat_models.vertexai'] = MagicMock()

import os
import json
import asyncio
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

# Import đồ thị RAG hiện tại của bạn
from agent_graph import app_graph

async def run_evaluation():
    print("🚀 BẮT ĐẦU QUY TRÌNH ĐÁNH GIÁ RAGAs...")

    # 1. Đọc Golden Dataset
    with open("golden_dataset.json", "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    questions = []
    ground_truths = []
    answers = []
    contexts = []

    print(f"📥 Đã nạp {len(eval_data)} câu hỏi test. Đang thu thập câu trả lời từ hệ thống...")

    # 2. Chạy Inference (Cho hệ thống làm bài thi)
    for i, item in enumerate(eval_data):
        q = item["question"]
        print(f"   -> Đang xử lý Q{i+1}: {q}")
        
        # Gọi đồ thị của bạn để lấy kết quả
        initial_state = {
            "question": q,
            "intent": "",
            "context": "",
            "answer": "",
            "chat_history": []
        }
        
        result_state = await app_graph.ainvoke(initial_state)
        
        questions.append(q)
        ground_truths.append(item["ground_truth"])
        
        # Bóc tách câu trả lời (bỏ phần <thinking> nếu có)
        raw_ans = result_state["answer"]
        ans_clean = raw_ans.split("Final Answer:")[-1].strip() if "Final Answer:" in raw_ans else raw_ans
        answers.append(ans_clean)
        
        # RAGAs yêu cầu contexts phải là List[str]
        contexts.append([result_state["context"]])

    # 3. Chuẩn bị dữ liệu cho RAGAs
    data_dict = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    dataset = Dataset.from_dict(data_dict)

    # 4. Khởi tạo Giám khảo (Judge)
    print("\n⚖️ Đang gọi Giám khảo Llama 70B để chấm điểm (quá trình này có thể mất vài phút)...")
    judge_llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    judge_embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")

    # 5. Tiến hành chấm điểm
    result = evaluate(
        dataset=dataset,
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        ],
        llm=judge_llm,
        embeddings=judge_embeddings
    )

    # 6. Xuất báo cáo
    df_result = result.to_pandas()
    
    print("\n" + "="*50)
    print("📊 KẾT QUẢ ĐÁNH GIÁ (0.0 đến 1.0):")
    print("="*50)
    print(f"Context Precision: {df_result['context_precision'].mean():.4f} (Độ chính xác của DB)")
    print(f"Context Recall:    {df_result['context_recall'].mean():.4f} (Độ bao phủ thông tin)")
    print(f"Faithfulness:      {df_result['faithfulness'].mean():.4f} (Độ trung thực, Zero Hallucination)")
    print(f"Answer Relevancy:  {df_result['answer_relevancy'].mean():.4f} (Độ bám sát câu hỏi)")
    print("="*50)

    # Lưu file CSV để tiện theo dõi
    df_result.to_csv("ragas_report.csv", index=False)
    print("\n✅ Đã lưu báo cáo chi tiết vào file 'ragas_report.csv'")

if __name__ == "__main__":
    asyncio.run(run_evaluation())