import numpy as np
from sentence_transformers import SentenceTransformer, util

class Reranker:
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def rerank(self, query, docs, top_k=None):
        """
        query: str
        docs: list of dict, each dict must have a 'title' and 'short_summary' (or 'content')
        top_k: int or None
        Returns: list of docs sorted by similarity to query
        """
        doc_texts = [d.get('short_summary') or d.get('content') or d.get('title','') for d in docs]
        query_emb = self.model.encode(query, convert_to_tensor=True)
        doc_embs = self.model.encode(doc_texts, convert_to_tensor=True)
        scores = util.cos_sim(query_emb, doc_embs)[0].cpu().numpy()
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        reranked_docs = [d for d, s in ranked]
        if top_k:
            reranked_docs = reranked_docs[:top_k]
        return reranked_docs
