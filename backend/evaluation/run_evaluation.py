"""
CLI entry point for the RAG evaluation framework.

Usage:
    python -m evaluation.run_evaluation                  # Full evaluation (20 samples)
    python -m evaluation.run_evaluation --dry-run        # Quick test (3 samples)
    python -m evaluation.run_evaluation --output results/ --max-samples 5
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.rag_evaluator import run_evaluation
from evaluation.report_generator import generate_html_report


def _print_summary(results: dict) -> None:
    """Prints a formatted summary table to stdout."""
    metrics = results["metrics"]
    metadata = results["metadata"]

    print("\n" + "=" * 68)
    print("  🧭  TRAVELO AI — RAG EVALUATION SUMMARY")
    print("=" * 68)
    print(f"  Samples:   {metadata['num_samples']}")
    print(f"  Duration:  {metadata['elapsed_seconds']}s")
    print(f"  Timestamp: {metadata['timestamp']}")
    print("-" * 68)
    print(f"  {'Metric':<25} {'Mean':>8} {'Min':>8} {'Max':>8} {'Std':>8}")
    print("-" * 68)

    indicators = {
        "faithfulness": "🛡️  Faithfulness",
        "answer_relevancy": "🎯 Answer Relevancy",
        "context_precision": "📌 Context Precision",
        "context_recall": "📚 Context Recall",
    }

    for key, label in indicators.items():
        data = metrics.get(key, {})
        mean = data.get("mean", "N/A")
        mn = data.get("min", "N/A")
        mx = data.get("max", "N/A")
        std = data.get("std", "N/A")

        mean_str = f"{mean:.4f}" if isinstance(mean, float) else str(mean)
        min_str = f"{mn:.4f}" if isinstance(mn, float) else str(mn)
        max_str = f"{mx:.4f}" if isinstance(mx, float) else str(mx)
        std_str = f"{std:.4f}" if isinstance(std, float) else str(std)

        # Color indicators for terminal
        if isinstance(mean, float):
            if mean >= 0.8:
                status = "✅"
            elif mean >= 0.6:
                status = "🟡"
            else:
                status = "🔴"
        else:
            status = "⚪"

        print(f"  {status} {label:<22} {mean_str:>8} {min_str:>8} {max_str:>8} {std_str:>8}")

    print("=" * 68)

    # Per-sample quick view
    print("\n  Per-Sample Highlights:")
    print("-" * 68)
    for i, sample in enumerate(results["per_sample"]):
        scores = sample.get("scores", {})
        faith = scores.get("faithfulness")
        relev = scores.get("answer_relevancy")
        faith_str = f"{faith:.2f}" if faith is not None else "N/A"
        relev_str = f"{relev:.2f}" if relev is not None else "N/A"
        print(
            f"  [{i+1:2d}] {sample['question'][:50]:<52} "
            f"F:{faith_str}  R:{relev_str}  [{sample['source']}]"
        )
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Travelo AI RAG Evaluation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m evaluation.run_evaluation                  Full eval (20 samples)
  python -m evaluation.run_evaluation --dry-run        Quick test (3 samples)
  python -m evaluation.run_evaluation --max-samples 5  Custom sample count
        """,
    )
    parser.add_argument(
        "--output",
        default="evaluation/results",
        help="Output directory for results (default: evaluation/results/)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit the number of evaluation samples",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Quick test with only 3 samples",
    )
    args = parser.parse_args()

    if args.dry_run:
        args.max_samples = 3

    # Run evaluation
    print("🚀 Starting RAG evaluation...\n")
    results = run_evaluation(max_samples=args.max_samples)

    # Print summary to stdout
    _print_summary(results)

    # Save JSON results
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(args.output, f"eval_results_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"📄 JSON results saved to: {json_path}")

    # Generate HTML report
    html_path = os.path.join(args.output, f"eval_report_{timestamp}.html")
    generate_html_report(results, html_path)
    print(f"📊 HTML report saved to:  {html_path}")

    # Also save a "latest" symlink-style copy for easy access
    latest_json = os.path.join(args.output, "eval_results_latest.json")
    latest_html = os.path.join(args.output, "eval_report_latest.html")
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    generate_html_report(results, latest_html)

    print(f"\n✅ Evaluation complete! Open {latest_html} in a browser to view the report.\n")


if __name__ == "__main__":
    main()
