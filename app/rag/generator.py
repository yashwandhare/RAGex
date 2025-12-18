import os
from google import genai
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Client
try:
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    logger.error(f"Gemini Client Error: {e}")
    client = None

def contextualize_question(question: str, history: list) -> str:
    """
    Rewrite question using history. 
    SYNC function to prevent SSL connection errors in threads.
    """
    if not history or not client: return question
    
    hist_txt = "\n".join([f"{m.get('role','user')}: {m.get('content','')}" for m in history[-3:]])
    
    prompt = f"""Rewrite the user's question to be a standalone search query based on the history.
    Resolve all pronouns (he, it, they). Keep it concise.
    
    History:
    {hist_txt}
    
    User Question: {question}
    
    Standalone Query:"""
    
    try:
        resp = client.models.generate_content(
            model=settings.LLM_MODEL, 
            contents=prompt
        )
        return resp.text.strip()
    except Exception as e:
        logger.error(f"Contextualize Error: {e}")
        return question

def generate_answer(question: str, contexts: list) -> dict:
    """
    Generate grounded answer.
    SYNC function to prevent SSL connection errors.
    """
    if not client: return {"answer": "AI Service Unavailable", "refusal": True}

    # Use all retrieved contexts
    context_text = "\n\n".join(contexts)
    
    # POLISHED PROMPT: Concise, Structure, No Fluff
    prompt = f"""You are a precise research assistant.
    Answer the question using ONLY the context provided below.
    
    Guidelines:
    1. **Be Concise:** Aim for 3-4 clear sentences.
    2. **Structure:** Use bullet points for lists.
    3. **Tone:** Professional and direct. No filler words.
    4. **Refusal:** If the answer is not in the context, say "I cannot find this information."
    
    Context:
    {context_text}
    
    Question: {question}
    """
    
    try:
        resp = client.models.generate_content(
            model=settings.LLM_MODEL, 
            contents=prompt
        )
        text = resp.text.strip()
        
        # Check for refusal keywords
        is_refusal = any(k in text.lower() for k in ["cannot find", "no information", "not mentioned"])
        
        return {"answer": text, "refusal": is_refusal}
    except Exception as e:
        logger.error(f"Generation Error: {e}")
        return {"answer": "Error generating answer.", "refusal": True}