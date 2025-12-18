# RAG

A Retrieval-Augmented Generation (RAG) system built with FastAPI that enables intelligent question-answering over web content.

## Features

- Web content crawling and indexing
- Vector-based semantic search using ChromaDB
- LLM-powered response generation
- RESTful API endpoints
- Simple web interface

## Tech Stack

- **FastAPI** - Web framework
- **ChromaDB** - Vector database
- **Google Gemini** - LLM for generation
- **BeautifulSoup4** - Web scraping
- **Sentence Transformers** - Embeddings

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yashwandhare/RAG-web.git
cd RAG-web
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export GOOGLE_API_KEY=your_api_key_here
```

## Usage

Start the server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Health check
- `POST /api/v1/index` - Index a URL
- `POST /api/v1/query` - Query the indexed content

## Development

Access the interactive API docs at `http://localhost:8000/docs`

## License

MIT License - see LICENSE file for details
