from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

class Settings(BaseSettings):
    """Centralized configuration with validation"""
    
    # API Keys
    GROQ_API_KEY: str = "gsk_..."
    
    # Model Configuration
    # Model can be changed via environment: LLM_MODEL
    LLM_MODEL: str = Field(default="llama-3.1-8b-instant", env="LLM_MODEL")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # RAG Parameters
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    DISTANCE_THRESHOLD: float = 0.75
    TOP_K_RESULTS: int = 10
    
    # Crawler Settings
    MAX_CRAWL_DEPTH: int = 3  # Increased to go deeper
    REQUEST_TIMEOUT: int = 30 
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # Performance
    MAX_WORKERS: int = 5
    MAX_PAGES_PER_INDEX: int = 50
    
    # Security & CORS
    CORS_ORIGINS: List[str] = ["*"]  
    
    # Database
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()