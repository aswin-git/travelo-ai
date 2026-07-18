# Travelo AI — Intelligent Travel Planning Agent

Travelo AI is a next-generation, conversational agentic travel platform designed to replace fragmented travel research. It orchestrates multiple intelligence engines to generate geographically optimized, hallucination-free itineraries based on real-world data and user constraints.

## 🚀 Core Features

- **Agentic Planning (LangGraph):** A 17-node state machine that autonomously gathers requirements, detects missing constraints (budget, dates), and routes intents.
- **Zero Hallucination RAG:** Uses ChromaDB (`all-MiniLM-L6-v2`) to inject factual Wikivoyage chunks into the LLM context, ensuring real-world accuracy.
- **Concurrent API Fetching:** Orchestrates parallel calls to SerpAPI (Places/Hotels), OpenWeather, and Crowd APIs to synthesize data in under 8 seconds.
- **Spatial Intelligence (Geo-Routing):** Computes Haversine distances to order attractions linearly and interleaves restaurants exactly where the user will physically be during meal slots.
- **Dynamic POI Scoring:** Custom heuristic engines rank hotels (out of 50) and restaurants based on rating, popularity, budget match, and context.

## 🛠 Tech Stack

### Frontend (Client-Side)
- **Framework:** React 19 (Vite)
- **Styling:** Tailwind CSS (Aurora Glassmorphism & Light modes)
- **Mapping:** Leaflet & React-Leaflet
- **Streaming:** Server-Sent Events (SSE) for low-latency generation
- **Auth:** Supabase

### Backend (Server-Side)
- **API Engine:** FastAPI (Python 3)
- **LLM Engine:** Google Gemini (`3.1-flash-lite-preview` for synthesis, `2.0-flash` for intent/eval)
- **Orchestration:** LangGraph (StateGraph Multi-Agent Architecture)
- **Databases:** 
  - PostgreSQL via Supabase (Relational & Caching)
  - ChromaDB (Vector/RAG)
  - Redis (Rate Limiting/TTL Caching)
- **External APIs:** SerpAPI, OpenWeather, Nominatim (OpenStreetMap)

## 🏗 Architecture (17-Node LangGraph)

The core logic operates as an advanced state machine:
1. **Setup:** `manage_history`, `classify_intent` (Gemini 2.0 JSON parsing + coreference resolution).
2. **Domain Handlers:** Dedicated nodes for `handle_itinerary`, `handle_hotel_search`, `handle_restaurants`, `handle_attractions`, `handle_directions`, etc.
3. **Conversational Modifiers:** Nodes to dynamically search and add places to existing itineraries mid-conversation.
4. **Synthesis:** Aggregated JSON is passed to Gemini 3.1 to generate the final itinerary narrative.

## ☁️ Production Deployment (GCP)

Fully automated serverless architecture on Google Cloud Platform:
- **Compute:** Cloud Run (`travelo-backend` & `travelo-frontend`).
- **Storage:** Cloud SQL (PostgreSQL) + GCS buckets mounted for ChromaDB persistence.
- **CI/CD:** Google Cloud Build automates Docker image builds (Artifact Registry) and deployments on main branch pushes.

## 📊 Evaluation & Baselines

Automated `rag_evaluator` metrics (Sample Size: 20):
- **Faithfulness:** 0.92
- **Answer Relevancy:** 0.83
- **Context Precision:** 0.81
- **Context Recall:** 0.71
