from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """
    Centralized configuration for the RAG Backend.
    """
    
    # ==================== API Keys ====================
    GOOGLE_API_KEY: str
    
    # ==================== Model Config ====================
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # ==================== RAG Parameters ====================
    # Increased chunk size to capture full definitions (e.g., "Founder Mode")
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # Retrieval Thresholds
    # Relaxed to 0.82 to allow broader matching for short queries like "Who is the writer?"
    DISTANCE_THRESHOLD: float = 0.82
    TOP_K_RESULTS: int = 15  # Retrieve more context to find deep answers
    
    # ==================== Crawler Settings ====================
    MAX_CRAWL_DEPTH: int = 3
    REQUEST_TIMEOUT: int = 15
    USER_AGENT: str = "Mozilla/5.0 (RAG-Bot/2.0)"
    MAX_WORKERS: int = 5
    MAX_PAGES_PER_INDEX: int = 50
    
    # ==================== Application ====================
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()