import google.generativeai as genai
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

def summarize_place(place_name: str, context: str = "") -> str:
    """Uses Gemini to summarize the place description in a conversational way."""
    prompt = f"""
    You are a travel assistant.
    Summarize the following tourist place in 2 concise and engaging sentences for travelers.
    
    Place: {place_name}
    Context: {context}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return "I'm sorry, I couldn't generate a description for this place right now."

def chat_with_context(query: str, context: str) -> str:
    """Uses Gemini to answer a query using the provided context (RAG)."""
    prompt = f"""
    You are an AI travel assistant. Answer the user's query about a tourist place based on the provided context.
    Keep your response concise, engaging, and directly answering the user. If the context doesn't have the answer, just give a general helpful summary based on the context.

    Context: {context}
    
    User Query: {query}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return "I'm sorry, I encountered an error while processing your request."

def summarize_reviews(reviews_text: str, subject_name: str) -> str:
    """Uses Gemini to summarize a list of reviews into a concise user experience summary."""
    prompt = f"""
    You are a travel assistant. Below is a list of user reviews for '{subject_name}'. 
    Please provide a concise summary (3-4 sentences) that captures the general consensus, 
    mentioning common pros and cons if applicable. Focus on what real users experience.
    
    Reviews:
    {reviews_text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return f"I couldn't summarize the reviews for {subject_name} at this time."
