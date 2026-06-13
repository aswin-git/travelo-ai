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

    prompt = f"""You are an expert AI travel assistant. Answer the user's query about a tourist place based on the provided context.

RESPONSE MODE — CHOOSE ONE:

**MODE A – SPECIFIC QUESTION** (e.g. "is X good for hindi speakers?", "is X safe for solo travelers?", "what food should I try in X?", "can I visit X in monsoon?"):
- Answer the question DIRECTLY — do NOT include a generic Overview or Weather section
- Use bullet points (- ) for easy scanning, NOT paragraphs
- Use **bold** for key facts and place names
- Keep it focused: only include information that answers the question
- Use a single relevant emoji header if needed (e.g. 💬 Language, 🛡️ Safety, 🍽️ Food)
- Be concise but thorough — cover the question fully, then stop

**MODE B – GENERAL PLACE QUERY** (e.g. "tell me about X", "I want to visit X", or very broad queries):
- Structure your response with clear markdown sections using ## headers
- Use bullet points (- ) for lists of items
- Use **bold** for important names, places, and key facts
- Use emojis to make headers engaging (e.g. 🌍 Overview, 🌤️ Weather, 🍽️ Food, 🏛️ Must Visit)
- NEVER dump information as a single paragraph
- Include relevant sections from: 🌍 Overview, ✨ Highlights, 🌤️ Current Weather, 🏛️ Must-Visit Spots, 🍽️ Local Cuisine, 📅 Best Time to Visit, 💡 Travel Tips, 🏰 History & Culture
- Only include sections for which you have actual information. Don't fabricate sections with no data.

GENERAL RULES (both modes):
- Use the conversation history (if any) to understand references like "there", "that place", etc.
- Keep each point focused and informative
- NEVER dump information as a wall of text — always use bullet points or short lines
{history_block}
Context: {context}

User Query: {query}"""
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
    prompt = f"""You are an expert travel writer. Analyze the following raw data about '{place_name}':
    {raw_context}
    
    Output a strictly formatted JSON object containing exactly these keys:
    - "overview": A vivid 4-5 sentence travel overview covering geography, vibe, and what makes this place unique.
    - "history_and_culture": Rich historical and cultural context — major events, traditions, cultural identity, and significance (3-4 sentences minimum).
    - "best_time_to_visit": Detailed seasonal breakdown — weather patterns, peak vs off-peak, festivals by month, and what to expect in each season.
    - "neighborhoods_districts": Key areas/neighborhoods to explore with brief descriptions of each (mention at least 3-4 if it's a city).
    - "local_delicacies": Traditional local foods they must try — name specific dishes, drinks, street food, and where to find them.
    - "things_to_do": Top 5-8 activities with brief descriptions (e.g., surfing, hiking, temple visits, boat rides, market walks).
    - "getting_around": Local transportation options — how to get there and move within the place (buses, trains, tuk-tuks, ferries, etc.).
    - "accommodation_tips": Types of stays available — budget hostels to luxury resorts, popular areas to stay.
    - "hidden_gems": 2-3 off-the-beaten-path experiences or lesser-known spots that most tourists miss.
    - "safety_tips": Practical safety advice, common scams to avoid, and general travel precautions.
    
    Each value should be a detailed, informative paragraph (not a list). Write as if you're crafting a premium travel guide.
    If information for a key is missing from the raw data, provide a reasonable, helpful fallback based on general knowledge — NEVER say 'Information not available'.
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
            "things_to_do": "Information currently unavailable.",
            "getting_around": "Information currently unavailable.",
            "accommodation_tips": "Information currently unavailable.",
            "hidden_gems": "Information currently unavailable.",
            "safety_tips": "Information currently unavailable.",
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