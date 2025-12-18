"""
RAG Backend - Main Application Entry Point
===========================================
"""
from dotenv import load_dotenv
import os

# 1. Load Env
load_dotenv()

# 2. Fix Tokenizer Warning (Must be done before importing libs that use tokenizers)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.index import router
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

app = FastAPI(
    title="RAG Backend",
    description="Production-grade Retrieval-Augmented Generation system",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error_detail = str(exc) if settings.ENVIRONMENT == "development" else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": error_detail}
    )

app.include_router(router, prefix="/api/v1", tags=["RAG"])

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "RAG Backend", "version": "2.0.0"}

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 RAG Backend Starting...")
    
    api_key = os.getenv("GROQ_API_KEY") 
    if api_key:
        logger.info(f"✅ Groq API Key loaded: {api_key[:5]}...")
    else:
        logger.error("❌ GROQ_API_KEY not found in environment!")
    
    logger.info("✅ RAG Backend ready to serve requests")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 RAG Backend shutting down gracefully...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")