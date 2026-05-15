"""
Adapters to make the project's Gemini model and SentenceTransformer embedding model
compatible with RAGAS v0.4.x evaluation interface.

RAGAS v0.4.x expects:
  - An LLM via llm_factory() with a client instance
  - Embeddings via a BaseRagasEmbeddings subclass
"""

import os
import sys
import typing as t

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google import genai
from ragas.llms import llm_factory
from ragas.embeddings.base import BaseRagasEmbeddings
from sentence_transformers import SentenceTransformer
from app.config import settings


# ── LLM Wrapper ──────────────────────────────────────────────────────────────

def get_ragas_llm():
    """Returns a RAGAS-compatible LLM using the project's Gemini API key.

    Uses the ragas llm_factory with a Google GenAI client instance.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    return llm_factory(
        model="gemini-3.1-flash-lite-preview",
        provider="google",
        client=client,
    )


# ── Embeddings Wrapper ───────────────────────────────────────────────────────

class SentenceTransformerRagasEmbeddings(BaseRagasEmbeddings):
    """Wraps SentenceTransformer in the RAGAS BaseRagasEmbeddings interface
    so RAGAS can use the same embedding model as our production pipeline."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def embed_query(self, text: str) -> t.List[float]:
        return self._model.encode(text, show_progress_bar=False).tolist()

    def embed_documents(self, texts: t.List[str]) -> t.List[t.List[float]]:
        return self._model.encode(texts, show_progress_bar=False).tolist()

    async def aembed_query(self, text: str) -> t.List[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: t.List[str]) -> t.List[t.List[float]]:
        return self.embed_documents(texts)


def get_ragas_embeddings() -> SentenceTransformerRagasEmbeddings:
    """Returns a RAGAS-compatible embeddings model using all-MiniLM-L6-v2."""
    return SentenceTransformerRagasEmbeddings()
