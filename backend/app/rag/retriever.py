from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class AdaptiveRetriever:
    def __init__(self, store):
        self.store = store

    async def retrieve(self, query: str, summary_mode: bool = False):
        # If summarizing, we want broad context, so we might relax the threshold
        threshold = settings.DISTANCE_THRESHOLD
        if len(query.split()) < 4: threshold -= 0.05
        
        # For summary, we might want more chunks to get a better overview
        k_results = settings.TOP_K_RESULTS + 5 if summary_mode else settings.TOP_K_RESULTS
        
        results = self.store.query(query, n_results=k_results)
        
        if not results['documents'] or not results['documents'][0]:
            return {"relevant": False, "contexts": [], "confidence": 0}

        docs = results['documents'][0]
        dists = results['distances'][0]
        metas = results['metadatas'][0]
        
        valid = []
        for doc, dist, meta in zip(docs, dists, metas):
            # In summary mode, we accept ANY result returned by the vector store
            # regardless of distance, because "summarize" queries often have poor 
            # semantic overlap with content but we still need the text.
            if summary_mode or dist < threshold:
                valid.append({"text": doc, "source": meta["source"], "dist": dist})
        
        if not valid:
            return {"relevant": False, "contexts": [], "confidence": 0}

        return {
            "relevant": True,
            "contexts": [v["text"] for v in valid],
            "sources": list(set(v["source"] for v in valid)),
            "confidence": 1 - valid[0]["dist"]
        }