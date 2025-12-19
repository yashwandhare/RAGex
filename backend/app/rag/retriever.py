from typing import Any, Dict, List

from app.core.config import settings
from app.core.logger import setup_logger
from app.rag.generator import generate_hyde_doc

logger = setup_logger(__name__)

class AdaptiveRetriever:
    """Hybrid retriever that augments vector search with HyDE when needed."""

    def __init__(self, store: Any) -> None:
        self.store = store

    async def retrieve(self, query: str, summary_mode: bool = False) -> Dict[str, Any]:
        # 1. Standard Vector Search
        threshold = settings.DISTANCE_THRESHOLD
        if len(query.split()) < 4: threshold -= 0.05
        
        k_results = settings.TOP_K_RESULTS + 5 if summary_mode else settings.TOP_K_RESULTS
        
        results = self.store.query(query, n_results=k_results)
        
        # Helper to process results
        def process_results(raw_res):
            if not raw_res["documents"] or not raw_res["documents"][0]:
                return []
            docs = raw_res["documents"][0]
            dists = raw_res["distances"][0]
            metas = raw_res["metadatas"][0]
            
            valid_items = []
            for doc, dist, meta in zip(docs, dists, metas):
                # In summary mode, accept almost anything. In query mode, enforce threshold.
                if summary_mode or dist < threshold:
                    valid_items.append(
                        {
                            "text": doc,
                            "source": meta.get("source"),
                            "dist": dist,
                        }
                    )
            return valid_items

        valid = process_results(results)
        
        # 2. HyDE Boost (Smart Automation)
        # If we found nothing or confidence is low, generate a hallucination and search with THAT.
        best_confidence = 1 - valid[0]["dist"] if valid else 0
        
        if not summary_mode and (not valid or best_confidence < 0.35):
            logger.info(f"🧠 Engaging HyDE for difficult query: '{query}'")
            hypothetical_answer = generate_hyde_doc(query)
            logger.debug(f"   HyDE Document: {hypothetical_answer[:50]}...")
            
            # Search again with the hypothetical answer
            hyde_results = self.store.query(hypothetical_answer, n_results=k_results)
            hyde_valid = process_results(hyde_results)
            
            # Merge unique results
            existing_texts = {v["text"] for v in valid}
            for item in hyde_valid:
                if item["text"] not in existing_texts:
                    valid.append(item)
            
            # Re-sort by distance
            valid.sort(key=lambda x: x["dist"])

        if not valid:
            return {
                "relevant": False,
                "contexts": [],
                "context_sources": [],
                "confidence": 0,
            }

        return {
            "relevant": True,
            "contexts": [v["text"] for v in valid],
            "context_sources": [v["source"] for v in valid],
            "sources": list({v["source"] for v in valid if v["source"]}),
            "confidence": 1 - valid[0]["dist"],
        }