from datetime import datetime
from typing import List

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import setup_logger
from app.rag.chunker import chunk_pages_smart
from app.rag.crawler import crawl_site_async
from app.rag.generator import analyze_content, contextualize_question, generate_answer
from app.rag.retriever import AdaptiveRetriever
from app.rag.store import VectorStore

logger = setup_logger(__name__)
router = APIRouter()

store = VectorStore()
retriever = AdaptiveRetriever(store)

class IndexRequest(BaseModel):
    """Request body for indexing a new website."""
    url: str
    max_pages: int = Field(default=10, ge=1, le=settings.MAX_PAGES_PER_INDEX)
    max_depth: int = Field(default=2, ge=1, le=settings.MAX_CRAWL_DEPTH)

class Message(BaseModel):
    """Single chat message used to build conversational history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)

class QueryRequest(BaseModel):
    """Query payload for asking questions against the indexed content."""
    question: str = Field(..., min_length=1)
    history: List[Message] = Field(default_factory=list)
    include_sources: bool = True
    debug: bool = False
    url: str | None = None  # Optional: limit summaries to a specific page URL

# New Model for Analytics
class AnalysisResponse(BaseModel):
    """Structured response returned from the analytics endpoint."""
    topics: List[str]
    type: str
    summary: str


class AnalyzeRequest(BaseModel):
    """Request payload for content analysis constrained to a specific URL."""
    url: str

async def process_indexing(url: str, max_pages: int, max_depth: int) -> None:
    try:
        logger.info(f"🚀 Starting background crawl: {url}")
        # Clear any existing index so new scans never mix with old data
        store.clear()
        pages = await crawl_site_async(url, max_pages, max_depth)
        
        if not pages:
            logger.error(f"❌ Indexing ABORTED: No content found at {url}.")
            store.clear()
            store.add([{
                "id": "error_msg", 
                "text": f"System Alert: The website {url} could not be indexed. It might be blocking bots or have no text content.", 
                "source": "system"
            }])
            return

        chunks = chunk_pages_smart(pages)
        if not chunks:
            logger.error("❌ Indexing Failed: Content found but chunking produced 0 results.")
            return

        store.clear()
        store.add(chunks)
        logger.info(f"✅ Indexing complete. Added {len(chunks)} chunks.")
        
    except Exception as e:
        logger.error(f"❌ Indexing failed exception: {e}")

@router.post("/index")
async def index_endpoint(req: IndexRequest, tasks: BackgroundTasks) -> dict:
    tasks.add_task(process_indexing, req.url, req.max_pages, req.max_depth)
    return {"status": "accepted", "message": "Indexing started."}

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(req: AnalyzeRequest) -> AnalysisResponse:
    """
    Smart Analytics: Inspect the vector store focusing on a single URL.

    Only chunks whose `source` matches the requested URL are considered for the
    analysis. If nothing matches, we gracefully fall back to a best‑effort
    analysis over all content (to avoid hard failures in edge cases).
    """
    results = store.query("summary overview introduction", n_results=20)

    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []

    filtered_contexts: List[str] = []
    if documents and metadatas and documents[0] and metadatas[0]:
        for doc, meta in zip(documents[0], metadatas[0]):
            source = (meta or {}).get("source")
            if source == req.url:
                filtered_contexts.append(doc)

    # If we have URL‑specific contexts, only proceed once those exist.
    if not filtered_contexts:
        return AnalysisResponse(
            topics=[],
            type="Empty",
            summary="Indexing in progress or no content for this URL yet.",
        )

    analysis = analyze_content(filtered_contexts)
    return AnalysisResponse(
        topics=analysis.get("topics", []),
        type=analysis.get("type", "Web Content"),
        summary=analysis.get("summary", "Content indexed successfully."),
    )

@router.post("/query")
async def query_endpoint(req: QueryRequest) -> dict:
    start_time = datetime.now()
    
    is_summary = "summarize" in req.question.lower() or "summary" in req.question.lower()
    
    if is_summary:
        search_query = req.question
    else:
        q_dict = [m.dict() for m in req.history]
        search_query = contextualize_question(req.question, q_dict)
    
    retrieval = await retriever.retrieve(search_query, summary_mode=is_summary)
    
    if not retrieval["relevant"]:
        return {
            "answer": "I cannot find relevant information in the indexed content.",
            "refusal": True,
            "sources": [],
            "confidence": 0.0,
            "confidence_score": 0.0,
            "suggested_questions": []
        }
    
    contexts = retrieval["contexts"]
    context_sources = retrieval.get("context_sources") or []

    # For page summaries, restrict contexts to the exact URL when provided.
    if is_summary and req.url:
        filtered = [
            (text, src)
            for text, src in zip(contexts, context_sources)
            if src == req.url
        ]
        if filtered:
            contexts, _ = zip(*filtered)
            contexts = list(contexts)

    gen_result = generate_answer(req.question, contexts, summary_mode=is_summary)
    duration = (datetime.now() - start_time).total_seconds()
    
    # Ensure at least 2 follow-up questions are always present
    suggestions = gen_result.get("suggestions", []) or []
    if len(suggestions) < 2:
        base = req.question.rstrip(" ?.")
        fallback = [
            f"What else should I know about {base}?",
            f"Can you highlight any limitations or caveats about {base}?",
            f"Are there related topics on {base} that I should explore next?",
        ]
        for s in fallback:
            if len(suggestions) >= 3:
                break
            if s not in suggestions:
                suggestions.append(s)

    return {
        "answer": gen_result["answer"],
        "refusal": gen_result["refusal"],
        "confidence": "high" if retrieval["confidence"] > 0.7 else "medium",
        "confidence_score": retrieval["confidence"],
        "sources": retrieval["sources"] if req.include_sources else [],
        "suggested_questions": suggestions,
        "response_time": round(duration, 2)
    }