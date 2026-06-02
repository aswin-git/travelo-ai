import google.generativeai as genai
import json
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

async def chat_with_context(query: str, context: str, history: list = None) -> str:
    """Uses Gemini asynchronously to answer a query using the provided context (RAG).
    
    Args:
        query: The current user message.
        context: Retrieved context (RAG, hotel info, etc.).
        history: Optional list of prior conversation turns [{"role": ..., "content": ...}].
    """
    history_block = ""
    if history:
        formatted = "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
            for h in history[-10:]  # Last 10 messages to stay within token limits
        )
        history_block = f"\n    Previous conversation:\n    {formatted}\n"

    prompt = f"""
    You are an AI travel assistant. Answer the user's query about a tourist place based on the provided context.
    Keep your response concise, engaging, and directly answering the user. If the context doesn't have the answer, just give a general helpful summary based on the context.
    Use the conversation history (if any) to understand references like "there", "that place", etc.
    {history_block}
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

async def synthesize_place_knowledge(place_name: str, raw_context: str) -> dict:
    """Uses Gemini asynchronously to parse raw context into a structured JSON profile."""
    prompt = f"""
    You are an expert travel writer. Analyze the following raw data about '{place_name}':
    {raw_context}
    
    Output a strictly formatted JSON object containing exactly these keys:
    - "overview": 3-4 sentences of general travel vibe.
    - "history_and_culture": Deep historical and cultural context.
    - "best_time_to_visit": Weather and seasonal tourist details.
    - "neighborhoods_districts": Key parts of the town to explore.
    - "local_delicacies": Traditional local foods they must try.
    - "things_to_do": Top activities, e.g., surfing, hiking, paragliding.
    
    If information for a key is missing, provide a generic reasonable fallback or say 'Information not available'.
    """
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Gemini generation error in synthesize_place_knowledge for '{place_name}': {e}", exc_info=True)
        return {
            "overview": "Information currently unavailable.",
            "history_and_culture": "Information currently unavailable.",
            "best_time_to_visit": "Information currently unavailable.",
            "neighborhoods_districts": "Information currently unavailable.",
            "local_delicacies": "Information currently unavailable.",
            "things_to_do": "Information currently unavailable."
        }

async def discover_and_recommend(user_query: str, retrieved_places: str) -> dict:
    """Uses Gemini to recommend places based on semantic search hits or to guess places if hits are poor."""
    prompt = f"""
    You are an enthusiastic travel advisor. The user is looking for this vibe/preference: "{user_query}"
    
    Here are the closest matches from our database:
    {retrieved_places}
    
    If the matches above clearly fit the user's vibe:
    - Recommend the best options from the database matches.
    - Explain exactly why they fit.
    - Set 'trigger_ingestion' to an empty list [].
    
    If the matches above DO NOT fit well (or are empty):
    - Recommend 2-3 real-world travel destinations that perfectly fit the vibe.
    - Set 'trigger_ingestion' to a list of those 2-3 destination names so we can add them to our database.
    
    Output strictly as JSON with keys 'response' and 'trigger_ingestion'.
    """
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Gemini generation error in discover_and_recommend: {e}", exc_info=True)
        return {
            "response": "I'm sorry, I couldn't find a perfect recommendation right now.",
            "trigger_ingestion": []
        }