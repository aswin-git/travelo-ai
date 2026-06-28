"""
Core RAG evaluation engine.

Instruments the existing RAG pipeline (process_chat_query) to capture
retrieval context and generated answers, then scores them using RAGAS metrics.
"""

import os
import sys
import asyncio
import time
from datetime import datetime, timezone
from typing import Any

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas.metrics._faithfulness import Faithfulness
from ragas.metrics._answer_relevance import ResponseRelevancy
from ragas.metrics._context_precision import LLMContextPrecisionWithReference
from ragas.metrics._context_recall import LLMContextRecall

from app.database import SessionLocal
from app.services.place_service import get_place_by_name
from app.services.chroma_service import query_documents
from app.services.rag_service import process_chat_query
from app.utils.logger import get_logger

from .gemini_adapter import get_ragas_llm, get_ragas_embeddings
from .eval_dataset import EVAL_DATASET

logger = get_logger(__name__)

# ChromaDB cosine-similarity threshold (mirrored from rag_service)
CHROMA_SIMILARITY_THRESHOLD = 0.5


def _retrieve_context(place_name: str, question: str, db) -> str:
    """Replays the retrieval step from process_chat_query to capture context.

    Returns the context string exactly as the RAG pipeline would build it
    (minus weather, which is runtime-only and not relevant for eval).

    Uses n_results=5 and queries ChromaDB with the user's question to match
    production retrieval behavior in rag_service.process_chat_query.
    """
    existing_place = get_place_by_name(db, place_name)

    if existing_place:
        context = existing_place.description or ""

        # Mirror production: fetch up to 5 chunks using the question and join them
        try:
            chroma_results = query_documents(question, n_results=5)
            if (
                chroma_results
                and chroma_results.get("documents")
                and chroma_results["documents"][0]
            ):
                docs = chroma_results["documents"][0]
                retrieved_facts = "\n\n".join(docs)
                context = f"=== General Description ===\n{context}\n\n=== Specific Retrieved Facts ===\n{retrieved_facts}"
                logger.info(f"Retrieved {len(docs)} chunks from ChromaDB for query: '{question}'")
        except Exception:
            logger.warning(f"ChromaDB query failed for '{question}', falling back to DB description")

        return context

    return ""


async def _collect_rag_outputs(samples: list[dict]) -> list[dict]:
    """Runs each evaluation sample through the actual RAG pipeline and
    captures the retrieval context + generated answer.

    Returns a list of dicts with keys:
        question, answer, contexts, ground_truth, source, place_name
    """
    collected = []
    db = SessionLocal()

    try:
        for i, sample in enumerate(samples):
            question = sample["question"]
            place_name = sample["place_name"]
            ground_truth = sample["ground_truth"]

            logger.info(f"[{i+1}/{len(samples)}] Evaluating: '{question}' (place={place_name})")

            # 1. Capture retrieval context (mirrors the retrieval step in process_chat_query)
            context = _retrieve_context(place_name, question, db)

            # 2. Run the full RAG pipeline to get the generated answer
            try:
                result = await process_chat_query(db, question, place_name)
                answer = result.get("response", "")
                source = result.get("source", "unknown")
            except Exception as e:
                logger.error(f"RAG pipeline error for '{question}': {e}", exc_info=True)
                answer = f"[ERROR] {e}"
                source = "error"

            collected.append({
                "question": question,
                "answer": answer,
                "contexts": [context] if context else ["No context retrieved."],
                "ground_truth": ground_truth,
                "source": source,
                "place_name": place_name,
            })

            # Small delay to respect API rate limits
            time.sleep(1)

    finally:
        db.close()

    return collected


def run_evaluation(
    samples: list[dict] | None = None,
    max_samples: int | None = None,
) -> dict[str, Any]:
    """Runs the full RAG evaluation pipeline.

    Args:
        samples: Optional custom dataset. Defaults to EVAL_DATASET.
        max_samples: Limit the number of samples (useful for quick dry-runs).

    Returns:
        A dict containing:
            - metrics: aggregate metric scores
            - per_sample: per-sample detailed results
            - metadata: run metadata (timestamp, model info, etc.)
    """
    if samples is None:
        samples = EVAL_DATASET

    if max_samples:
        samples = samples[:max_samples]

    logger.info(f"Starting RAG evaluation with {len(samples)} samples...")
    start_time = time.time()

    # Step 1: Collect RAG outputs
    collected = asyncio.run(_collect_rag_outputs(samples))

    # Step 2: Build RAGAS EvaluationDataset
    ragas_samples = []
    for c in collected:
        ragas_samples.append(
            SingleTurnSample(
                user_input=c["question"],
                response=c["answer"],
                retrieved_contexts=c["contexts"],
                reference=c["ground_truth"],
            )
        )
    eval_dataset = EvaluationDataset(samples=ragas_samples)

    # Step 3: Initialize RAGAS metrics and LLM/embeddings
    ragas_llm = get_ragas_llm()
    ragas_embeddings = get_ragas_embeddings()

    metrics = [
        Faithfulness(llm=ragas_llm),
        ResponseRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
        LLMContextPrecisionWithReference(llm=ragas_llm),
        LLMContextRecall(llm=ragas_llm),
    ]

    logger.info("Running RAGAS evaluation (this may take a few minutes)...")

    # Step 4: Run RAGAS evaluation
    results = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
    )

    elapsed = time.time() - start_time

    # Step 5: Structure the output
    results_df = results.to_pandas()

    metric_names = [
        "faithfulness",
        "answer_relevancy",
        "llm_context_precision_with_reference",
        "context_recall",
    ]

    aggregate_metrics = {}
    for metric in metric_names:
        if metric in results_df.columns:
            values = results_df[metric].dropna()
            if len(values) > 0:
                aggregate_metrics[metric] = {
                    "mean": round(float(values.mean()), 4),
                    "min": round(float(values.min()), 4),
                    "max": round(float(values.max()), 4),
                    "std": round(float(values.std()), 4) if len(values) > 1 else 0.0,
                }

    per_sample = []
    for i, row in results_df.iterrows():
        sample_result = {
            "question": collected[i]["question"],
            "place_name": collected[i]["place_name"],
            "answer": collected[i]["answer"],
            "context_snippet": collected[i]["contexts"][0][:200] + "..."
                if len(collected[i]["contexts"][0]) > 200
                else collected[i]["contexts"][0],
            "ground_truth_snippet": collected[i]["ground_truth"][:200] + "..."
                if len(collected[i]["ground_truth"]) > 200
                else collected[i]["ground_truth"],
            "source": collected[i]["source"],
            "scores": {},
        }
        for metric in metric_names:
            if metric in results_df.columns:
                val = row[metric]
                # NaN check: val != val is True for NaN
                sample_result["scores"][metric] = round(float(val), 4) if val == val else None

        per_sample.append(sample_result)

    return {
        "metrics": aggregate_metrics,
        "per_sample": per_sample,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_samples": len(samples),
            "elapsed_seconds": round(elapsed, 2),
            "embedding_model": "all-MiniLM-L6-v2",
            "llm_model": "gemini-2.0-flash (judge), gemini-3.1-flash-lite-preview (generation)",
            "chroma_similarity_threshold": CHROMA_SIMILARITY_THRESHOLD,
        },
    }
