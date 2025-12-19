"""
Smart Text Chunking with Semantic Boundaries
=============================================
Creates overlapping chunks from crawled pages while preserving context.
Implements multi-level quality filtering and deduplication.
"""
import re
from typing import List, Dict, Set
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)


def chunk_pages_smart(pages: List[Dict]) -> List[Dict]:
    """
    Create semantic chunks from crawled pages with overlap.
    
    Strategy:
    - Split on sentence boundaries (preserves meaning)
    - Add overlap between chunks (preserves context across boundaries)
    - Filter noise (boilerplate, footers, etc.)
    - Deduplicate identical chunks (hash-based)
    - Validate chunk quality (length, word count)
    
    Why sentence-based chunking?
    - Better semantic preservation than character-based
    - Overlap maintains context across boundaries
    - Improves retrieval accuracy
    
    Args:
        pages: List of page dicts with 'url', 'text', and 'depth'
    
    Returns:
        List[Dict]: Filtered, deduplicated chunks with id, text, and source
    """
    chunks = []
    seen_hashes: Set[int] = set()  # For deduplication
    
    # ==================== NOISE FILTERING BLACKLIST ====================
    # Common phrases in non-content areas (footers, cookie banners, etc.)
    # These are often repeated and don't provide useful information
    blacklist_phrases = [
        "all rights reserved",
        "privacy policy", 
        "cookie policy",
        "terms of use",
        "terms of service",
        "subscribe to newsletter",
        "follow us on",
        "sign up for",
        "copyright ©"
    ]
    
    logger.info(f"📄 Processing {len(pages)} pages for chunking...")
    
    for page_idx, page in enumerate(pages, 1):
        try:
            # ==================== EXTRACT PAGE DATA ====================
            text = page.get("text", "")
            url = page.get("url", "unknown")
            depth = page.get("depth", 0)
            
            # Skip empty pages
            if not text:
                logger.debug(f"   Page {page_idx}: Skipping (no text)")
                continue
            
            # ==================== NORMALIZE WHITESPACE ====================
            # Replace multiple spaces/newlines with single space
            # This makes sentence splitting more reliable
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Skip if normalized text is too short
            if len(text) < 50:
                logger.debug(f"   Page {page_idx}: Skipping (too short after normalization)")
                continue
            
            # ==================== SPLIT INTO SENTENCES ====================
            # Split on sentence boundaries: ., !, ? followed by space
            # This preserves semantic units better than arbitrary character counts
            sentences = re.split(r'(?<=[.!?])\s+', text)
            
            # Clean sentences and filter empty ones
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                logger.debug(f"   Page {page_idx}: Skipping (no valid sentences)")
                continue
            
            # ==================== CREATE CHUNKS WITH OVERLAP ====================
            current_chunk_sentences: List[str] = []
            current_chunk_length = 0
            chunk_id = 0
            page_chunk_count = 0
            
            for sentence in sentences:
                sentence_length = len(sentence)
                
                # Check if adding this sentence would exceed chunk size
                would_exceed = (current_chunk_length + sentence_length) > settings.CHUNK_SIZE
                has_content = len(current_chunk_sentences) > 0
                
                if would_exceed and has_content:
                    # ==================== SAVE CURRENT CHUNK ====================
                    chunk_text = " ".join(current_chunk_sentences)
                    
                    # Validate and potentially save this chunk
                    if _is_valid_chunk(chunk_text, blacklist_phrases, seen_hashes):
                        chunks.append({
                            "id": f"{url}::chunk_{chunk_id}",
                            "text": chunk_text,
                            "source": url,
                            "depth": depth,
                        })
                        chunk_id += 1
                        page_chunk_count += 1
                    
                    # ==================== CREATE OVERLAP ====================
                    # Keep last N characters worth of sentences
                    # This preserves context when chunks are split mid-topic
                    overlap_sentences = []
                    overlap_length = 0
                    
                    # Work backwards to build overlap
                    for sent in reversed(current_chunk_sentences):
                        if overlap_length >= settings.CHUNK_OVERLAP:
                            break
                        overlap_sentences.insert(0, sent)
                        overlap_length += len(sent)
                    
                    # Start new chunk with overlap
                    current_chunk_sentences = overlap_sentences
                    current_chunk_length = overlap_length
                
                # Add current sentence to chunk
                current_chunk_sentences.append(sentence)
                current_chunk_length += sentence_length
            
            # ==================== SAVE FINAL CHUNK ====================
            # Don't forget the last chunk for this page
            if current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                
                if _is_valid_chunk(chunk_text, blacklist_phrases, seen_hashes):
                    chunks.append({
                        "id": f"{url}::chunk_{chunk_id}",
                        "text": chunk_text,
                        "source": url,
                        "depth": depth,
                    })
                    page_chunk_count += 1
            
            logger.debug(f"   Page {page_idx}: Created {page_chunk_count} chunks")
            
        except Exception as e:
            # Log error but continue with other pages
            logger.warning(f"   Page {page_idx} chunking error: {e}")
            continue
    
    # ==================== SUMMARY ====================
    logger.info(f"✅ Chunking complete:")
    logger.info(f"   Total chunks created: {len(chunks)}")
    logger.info(f"   Average chunk size: {sum(len(c['text']) for c in chunks) // max(len(chunks), 1)} chars")
    logger.info(f"   Unique sources: {len(set(c['source'] for c in chunks))}")
    
    return chunks


def _is_valid_chunk(text: str, blacklist: List[str], seen_hashes: Set[int]) -> bool:
    """
    Validate chunk quality through multiple filters.
    
    Quality checks:
    1. Minimum length (prevents tiny meaningless chunks)
    2. Blacklist phrases (removes boilerplate)
    3. Deduplication (removes exact duplicates)
    4. Minimum word count (ensures substance)
    
    Why multiple filters?
    - Layered filtering catches different types of noise
    - Improves retrieval quality by removing junk
    - Reduces storage and processing overhead
    
    Args:
        text: Chunk text to validate
        blacklist: List of noise phrases to check
        seen_hashes: Set of already-seen chunk hashes
    
    Returns:
        bool: True if chunk passes all quality checks
    """
    # ==================== CHECK 1: MINIMUM LENGTH ====================
    # Very short chunks often lack context
    if len(text) < 50:
        return False
    
    # ==================== CHECK 2: BLACKLIST PHRASES ====================
    # Remove chunks that are primarily boilerplate
    text_lower = text.lower()
    
    for phrase in blacklist:
        if phrase in text_lower:
            # If blacklist phrase is substantial part of chunk, reject it
            # Allow phrase if it's just a small mention in larger content
            phrase_ratio = len(phrase) / len(text)
            if phrase_ratio > 0.3:  # More than 30% is blacklisted phrase
                return False
    
    # ==================== CHECK 3: DEDUPLICATION ====================
    # Reject exact duplicates (same hash)
    # This catches repeated content across pages
    text_hash = hash(text)
    
    if text_hash in seen_hashes:
        return False
    
    # Add to seen set for future checks
    seen_hashes.add(text_hash)
    
    # ==================== CHECK 4: MINIMUM WORD COUNT ====================
    # Ensure chunk has substantial content
    # Filters out chunks that are just numbers, symbols, or sparse text
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    if word_count < 10:
        return False
    
    # ==================== CHECK 5: WORD DENSITY ====================
    # Reject chunks with very low word density (mostly symbols/spaces)
    # This catches malformed content that passed previous checks
    char_count = len(text)
    avg_word_length = sum(len(w) for w in words) / max(word_count, 1)
    
    # Average word length should be reasonable (2-15 chars)
    # If it's too short, might be just symbols/numbers
    if avg_word_length < 2:
        return False
    
    # All checks passed!
    return True