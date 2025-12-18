# RAGex

RAGex is a Retrieval-Augmented Generation (RAG) system with a FastAPI backend and a modern glassmorphic web UI. It crawls pages, builds a local vector index, and answers questions or summaries against that context using Groq-hosted Llama 3.1.

## Features

- 🕷️ Web crawling and indexing (HTML-first; no JS execution)
- 🔍 Vector semantic search with ChromaDB
- 🤖 Groq Llama 3.1 (default: llama-3.1-8b-instant) for answers
- 📄 One-click page summarization
- 🎯 Adaptive retrieval with confidence scoring
- 💬 Follow-up question suggestions
- 💻 Glassmorphic, smooth-scrolling web interface
- ⚙️ Environment-based configuration (LLM model, API keys)

## Current limitations

- Images/OCR, PDF/DOCX/PPTX, and YouTube transcripts are not yet implemented.
- No JavaScript rendering: SPA-heavy or auth-gated pages may index partially. Use fully rendered/static pages for best results.

## Project Structure

```
RAGex/
├── backend/              # FastAPI backend service
│   ├── app/
│   │   ├── api/         # API endpoints
│   │   ├── core/        # Configuration & logging
│   │   ├── rag/         # RAG system (crawler, chunker, retriever, etc.)
│   │   └── main.py      # FastAPI application
│   ├── data/            # Database storage
│   │   └── chroma_db/   # Vector database
│   ├── requirements.txt
│   └── .env.example
├── frontend/            # Static web interface
│   └── index.html       # Single-page app
├── README.md
└── LICENSE
```

## Tech Stack

**Backend:**
- FastAPI - Modern Python web framework
- ChromaDB - Local vector database
- Groq API - Fast LLM inference (llama-3.1-8b-instant by default)
- aiohttp + BeautifulSoup4 - HTML crawling and parsing
- Sentence Transformers - Text embeddings (all-MiniLM-L6-v2)
- Pydantic Settings - Environment configuration

**Frontend:**
- Vanilla HTML/CSS/JS - No framework
- Glassmorphic design with backdrop filters
- FontAwesome icons
- Smooth scroll animations

## Quick Start

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Required
GROQ_API_KEY=your_key

# Optional
LLM_MODEL=llama-3.1-8b-instant
LOG_LEVEL=INFO
```

4. Start the API server:
```bash
uvicorn app.main:app --reload
```

Backend runs at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Serve with any static server:
```bash
python -m http.server 8080
```

Frontend runs at: `http://localhost:8080`

## API Endpoints

- `GET /` - Health check
- `POST /api/v1/index` - Index a URL for RAG
  - Request: `{"url": "https://example.com"}`
  - Returns indexed content with metadata
- `POST /api/v1/query` - Query indexed content
  - Request: `{"question": "Your question here"}`
  - Returns answer with sources, confidence score, and follow-up questions
  - "summarize this page" triggers summary mode

## Usage

1) Index a page
- Provide a URL in the UI and click Connect. The backend fetches HTML, chunks it, embeds, and stores in ChromaDB.

2) Ask questions or summaries
- Ask specific questions for targeted retrieval, or type "summarize this page" for broader coverage.

3) Review answers
- Responses include cited sources, a confidence score, and suggested follow-ups.

## Roadmap

- JS rendering for SPA-heavy pages (Playwright)
- PDF/DOCX/PPTX ingestion
- Image/OCR support
- YouTube transcript ingestion

## Development

The backend and frontend are completely decoupled and communicate only via REST API. You can:
- Run them on different ports/servers
- Deploy them separately
- Replace the frontend with any other client (mobile app, CLI, etc.)

## License

MIT License - see [LICENSE](LICENSE) file for details
