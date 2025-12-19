from __future__ import annotations

import json
from typing import Dict, List, Optional

from openai import OpenAI

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Groq Client
try:
    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    logger.info(f"✅ Groq Client Configured (Model: {settings.LLM_MODEL})")
except Exception as e:
    logger.error(f"❌ Failed to initialize Groq client: {e}")
    client = None

def contextualize_question(question: str, history: List[dict]) -> str:
    """
    Rewrite a raw user question into a search-optimized query using short history.

    Falls back to the original question if the LLM client is unavailable.
    """
    if "summarize" in question.lower():
        return question
    if not history or not client:
        return question
    
    messages = [{"role": "system", "content": "Rewrite the user's question to be a specific search query based on the history."}]
    for msg in history[-3:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append(
            {"role": role, "content": msg.get("content", "")}
        )
    messages.append({"role": "user", "content": f"Rewrite: {question}"})
    
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # On any upstream error, keep behaviour identical and simply return the
        # original question.
        return question

def generate_hyde_doc(question: str) -> str:
    """
    HyDE (Hypothetical Document Embeddings):
    Generates a fake 'perfect' answer to the question. 
    We embed this to find real documents that look like this answer.
    """
    if not client:
        return question
    
    system_msg = "You are a helpful assistant. Write a short, hypothetical paragraph that would perfectly answer the user's question. Do not ask questions, just write the answer content."
    
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": question},
            ],
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"HyDE generation failed: {e}")
        return question

def analyze_content(contexts: List[str]) -> Dict[str, object]:
    """
    Smart Analytics: Extracts topics, doc type, and summary from chunks.
    """
    if not client or not contexts:
        return {"topics": [], "type": "Unknown", "summary": "Analysis unavailable."}

    # Sample a few chunks to get the gist (first, middle, last)
    sample_text = "\n".join(contexts[:2] + contexts[-2:] if len(contexts) > 4 else contexts)
    
    prompt = (
        "Analyze the following text sample from a website.\n"
        "Return a JSON object with keys: 'topics' (list of 5 short strings), "
        "'type' (string, e.g., 'Documentation', 'News', 'Blog'), "
        "and 'summary' (one concise sentence).\n\n"
        f"Text Sample:\n{sample_text[:3000]}"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # Force JSON
            temperature=0.3,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        # Fallback if JSON fails
        return {"topics": ["General"], "type": "Web Content", "summary": "Content indexed successfully."}

def generate_answer(question: str, contexts: list, summary_mode: bool = False) -> dict:
    if not client: return {"answer": "AI Service Unavailable", "refusal": True, "suggestions": []}

    context_text = "\n\n".join(contexts)
    
    # ------------------ SMART PROMPT ------------------
    if summary_mode:
        system_content = (
            "You are a helpful research assistant. Summarize the provided text concisely. "
            "Synthesize the main points. If the content is fragmented, summarize what IS available. "
            "After the summary, output '<<<FOLLOWUP>>>' followed by 3 interesting follow-up questions."
        )
    else:
        system_content = (
            "You are an intelligent research assistant. Answer the user's question using ONLY the provided context.\n\n"
            "**CRITICAL REASONING RULES:**\n"
            "1. **Inference Allowed:** If the text explicitly mentions one thing (e.g., 'Only for Pixel'), you MUST infer the exclusion of others (e.g., answer 'No, it does not mention Samsung').\n"
            "2. **No Blind Refusals:** Do not just say 'I cannot find this'. Instead, state what *is* found.\n"
            "3. **Formatting:** Answer clearly. Then, output '<<<FOLLOWUP>>>' followed by 3 distinct follow-up questions."
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}"}
    ]
    
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=0.3
        )
        
        full_text = resp.choices[0].message.content.strip()
        suggestions = []
        answer_text = full_text

        # Parsing Logic
        if "<<<FOLLOWUP>>>" in full_text:
            parts = full_text.split("<<<FOLLOWUP>>>")
            answer_text = parts[0].strip()
            followup_text = parts[1].strip()
            # Remove common preambles
            for preamble in ["Here are three interesting follow-up questions:", "Here are some follow-up questions:", "Follow-up questions:"]:
                followup_text = followup_text.replace(preamble, "").strip()
            suggestions = [s.strip().lstrip('-•123. ') for s in followup_text.split('\n') if s.strip()]
        
        # Fallback
        if not suggestions:
             lines = full_text.split('\n')
             candidates = [l.strip().lstrip('-•123. ') for l in reversed(lines) if l.strip().endswith('?')]
             suggestions = candidates[:3]
             for s in suggestions: answer_text = answer_text.replace(s, "")

        answer_text = answer_text.replace("<<<FOLLOWUP>>>", "").strip()
        
        # Improved Refusal
        is_refusal = False
        if not context_text or ("i cannot find" in answer_text.lower() and len(answer_text) < 50):
            is_refusal = True

        return {
            "answer": answer_text, 
            "refusal": is_refusal, 
            "suggestions": suggestions[:3] 
        }
        
    except Exception as e:
        logger.error(f"Generation Error: {e}")
        return {"answer": "Error generating answer.", "refusal": True, "suggestions": []}