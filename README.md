# DISHA AI: Agentic Intelligent Travel Decision Platform

DISHA AI is a next-generation, agentic travel platform designed to provide hyper-personalized travel decisions. By orchestrating multiple specialized intelligence engines, DISHA AI transforms fragmented travel data into cohesive, time-optimized, and context-aware travel experiences.

## 🧠 Modular Architecture

DISHA AI is built on a sophisticated multi-agent architecture, consisting of 12 specialized modules:

### 1. Master Orchestrator Agent
- **Intent & Memory**: Understands user intent and maintains session memory across multi-turn conversations.
- **Clarification**: Detects missing trip details and asks targeted clarifying questions.
- **Dynamic Activation**: Activates relevant engines based on user context and merges outputs into a single coherent response.

### 2. Travel Discovery Engine
- **Style-Based Discovery**: Suggests top places and neighborhoods based on traveler style (relaxing, food-focused, cultural, nightlife, adventure).
- **Hidden Gems**: Recommends off-the-beaten-path spots alongside mainstream attractions.

### 3. Hotel Intelligence Engine
- **Multi-Factor Scoring**: Ranks hotels based on Review Quality (25%), Price Fit (20%), Location (20%), Amenities (15%), Comfort (10%), and Weather Suitability (10%).
- **Smart Filtering**: Filters out unavailable, out-of-budget, and low-quality results in the first pass.

### 4. Restaurant Intelligence Engine
- **Contextual Matching**: Matches cuisine preferences, meal-time context, and budget constraints.
- **Sentiment Scoring**: Analyzes hygiene and food quality through review sentiment analysis.
- **Real-Time Status**: Checks real-time opening status and proximity.

### 5. Tourist Places Engine
- **Suitability Flagging**: Flags attractions for indoor/outdoor suitability and estimates crowd levels/time required.
- **Profile Adaptation**: Adjusts recommendations for family, couple, or solo traveler profiles.
- **Weather-Adaptive**: Boosts indoor places during rain and deprioritizes outdoor spots like beaches.

### 6. Weather Engine
- **Live Forecasts**: Fetches destination weather via OpenWeather API for specific travel dates.
- **Decision Logic**: High rain probability triggers itinerary adjustments, prioritizing indoor locations and transport options like cabs/metro.

### 7. Review Intelligence Engine
- **Quick Summaries**: Provides clean, concise card summaries of user experiences.
- **Ask AI (RAG)**: Allows users to ask specific questions (e.g., "Is this hotel good for elderly parents?") and receive cited answers using Retrieval-Augmented Generation.

### 8. Transport Optimization Engine
- **Graph Modeling**: Models the transport network (metro, bus, ferry, airport) as a graph.
- **Multi-Objective Routing**: Uses Dijkstra/A* algorithms to find the fastest, cheapest, or least-transfer routes.

### 9. RAG Knowledge Engine
- **Grounded Chat**: A factual travel chatbot grounded in tourism portals, seasonal guides, and local travel tips.
- **Semantic Search**: Uses embedding search to retrieve relevant chunks for accurate, cited responses.

### 10. Ranking Engine
- **Personalized Decision Layer**: The core layer that determines the final ordering of all recommendations.
- **Dynamic Weighting**: Weights (Reviews, Price, Location, etc.) adjust dynamically based on traveler type (Family vs. Solo vs. Business).

### 11. Itinerary Generator
- **Coherent Planning**: Integrates outputs from all engines into a complete, day-wise, time-optimized schedule.
- **Seamless Flow**: Manages transitions between check-in, meals, attractions, and transport.

### 12. Booking Agent (Future Phase)
- **Direct Transactions**: Will allow booking hotels and reserving restaurants directly through the platform.
- **Price Alerts**: Future support for fare drop notifications and pre-filled booking handoffs.

---

## 🛠 Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **LLM**: [Google Gemini](https://aistudio.google.com/) (Flash & Pro models)
- **Orchestration**: [LangGraph / LangChain](https://python.langchain.com/docs/langgraph)
- **Vector Database**: [ChromaDB](https://www.trychroma.com/)
- **Primary Database**: [PostgreSQL](https://www.postgresql.org/)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **Integrations**: [SerpAPI](https://serpapi.com/) (Google Hotels/Maps), [OpenStreetMap](https://www.openstreetmap.org/), [Wikipedia REST API](https://www.wikipedia.org/), [OpenWeatherMap](https://openweathermap.org/api).

### Frontend
- **Framework**: [React](https://reactjs.org/) (Vite)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Design**: Premium, modern UI with a focus on visual excellence and micro-animations.

---
