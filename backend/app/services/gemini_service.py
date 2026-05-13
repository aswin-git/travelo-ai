import google.generativeai as genai
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# Keeping flash-lite as it's built for speed, which is exactly what you need here.
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

async def summarize_place(place_name: str, context: str = "") -> str:
    """Uses Gemini asynchronously to summarize the place description in a conversational way."""
    prompt = f"""
    You are a travel assistant.
    Summarize the following tourist place in 2 concise and engaging sentences for travelers.
    
    Place: {place_name}
    Context: {context}
    """
    try:
        # AWAIT the async generation so the thread is freed up
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini generation error in summarize_place for '{place_name}': {e}", exc_info=True)
        return "I'm sorry, I couldn't generate a description for this place right now."

async def chat_with_context(query: str, context: str) -> str:
    """Uses Gemini asynchronously to answer a query using the provided context (RAG)."""
    prompt = f"""
    You are an AI travel assistant. Answer the user's query about a tourist place based on the provided context.
    Keep your response concise, engaging, and directly answering the user. If the context doesn't have the answer, just give a general helpful summary based on the context.

    Context: {context}
    
    User Query: {query}
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini generation error in chat_with_context: {e}", exc_info=True)
        return "I'm sorry, I encountered an error while processing your request."

async def summarize_reviews(reviews_text: str, subject_name: str) -> str:
    """Uses Gemini asynchronously to summarize a list of reviews into a concise user experience summary."""
    prompt = f"""
    You are a travel assistant. Below is a list of user reviews for '{subject_name}'. 
    Please provide a concise summary (3-4 sentences) that captures the general consensus, 
    mentioning common pros and cons if applicable. Focus on what real users experience.
    
    Reviews:
    {reviews_text}
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini generation error in summarize_reviews for '{subject_name}': {e}", exc_info=True)
        return f"I couldn't summarize the reviews for {subject_name} at this time."