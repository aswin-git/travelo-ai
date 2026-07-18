"""
HTML report generator for RAG evaluation results.

Produces a self-contained HTML file with:
- Aggregate metric scores with color-coded indicators
- Per-sample breakdown table
- Score distribution visualisation using inline CSS bar charts
"""

import os
from datetime import datetime


def _score_color(score: float | None) -> str:
    """Returns a CSS color class based on score threshold."""
    if score is None:
        return "#94a3b8"  # slate-400
    if score >= 0.8:
        return "#22c55e"  # green-500
    if score >= 0.6:
        return "#eab308"  # yellow-500
    return "#ef4444"  # red-500


def _score_badge(score: float | None) -> str:
    """Returns an HTML badge for a score value."""
    if score is None:
        return '<span style="color: #94a3b8;">N/A</span>'
    color = _score_color(score)
    return (
        f'<span style="display:inline-block; padding:2px 10px; border-radius:9999px; '
        f'background:{color}22; color:{color}; font-weight:600; font-size:0.9em;">'
        f'{score:.2f}</span>'
    )


def _bar_chart(score: float | None, width: int = 120) -> str:
    """Returns an inline CSS bar chart for a score."""
    if score is None:
        return '<div style="color:#94a3b8;">—</div>'
    color = _score_color(score)
    filled = int(score * width)
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="width:{width}px;height:8px;background:#1e293b;border-radius:4px;overflow:hidden;">'
        f'<div style="width:{filled}px;height:100%;background:{color};border-radius:4px;"></div>'
        f'</div>'
        f'<span style="font-size:0.85em;color:{color};font-weight:600;">{score:.2f}</span>'
        f'</div>'
    )


def generate_html_report(eval_results: dict, output_path: str) -> str:
    """Generates a self-contained HTML evaluation report.

    Args:
        eval_results: Output from rag_evaluator.run_evaluation()
        output_path: Path to write the HTML file

    Returns:
        The output_path for convenience.
    """
    metrics = eval_results["metrics"]
    per_sample = eval_results["per_sample"]
    metadata = eval_results["metadata"]

    metric_labels = {
        "faithfulness": ("Faithfulness", "Is the answer grounded in the retrieved context?"),
        "answer_relevancy": ("Answer Relevancy", "Does the answer address the user's question?"),
        "llm_context_precision_with_reference": ("Context Precision", "Is the retrieved context relevant?"),
        "context_recall": ("Context Recall", "Does the context contain needed information?"),
    }

    # ── Aggregate metrics cards ──────────────────────────────────────────
    metric_cards = ""
    for key, (label, desc) in metric_labels.items():
        data = metrics.get(key, {})
        mean = data.get("mean")
        color = _score_color(mean)
        metric_cards += f"""
        <div style="background:#1e293b; border-radius:12px; padding:24px; flex:1; min-width:200px;
                     border:1px solid {color}33;">
            <div style="font-size:0.85em; color:#94a3b8; margin-bottom:4px;">{label}</div>
            <div style="font-size:2.2em; font-weight:700; color:{color};">{f'{mean:.2f}' if mean is not None else 'N/A'}</div>
            <div style="font-size:0.75em; color:#64748b; margin-top:6px;">{desc}</div>
            <div style="font-size:0.75em; color:#475569; margin-top:8px;">
                min: {data.get('min', 'N/A')} &nbsp;|&nbsp; max: {data.get('max', 'N/A')} &nbsp;|&nbsp; std: {data.get('std', 'N/A')}
            </div>
        </div>
        """

    # ── Per-sample table rows ────────────────────────────────────────────
    table_rows = ""
    for i, sample in enumerate(per_sample):
        scores = sample.get("scores", {})
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e293b;">
            <td style="padding:12px 8px; color:#e2e8f0; font-size:0.85em; max-width:120px; word-wrap:break-word;">{sample['place_name']}</td>
            <td style="padding:12px 8px; color:#cbd5e1; font-size:0.85em; max-width:250px; word-wrap:break-word;">{sample['question']}</td>
            <td style="padding:12px 8px;">{_bar_chart(scores.get('faithfulness'))}</td>
            <td style="padding:12px 8px;">{_bar_chart(scores.get('answer_relevancy'))}</td>
            <td style="padding:12px 8px;">{_bar_chart(scores.get('llm_context_precision_with_reference'))}</td>
            <td style="padding:12px 8px;">{_bar_chart(scores.get('context_recall'))}</td>
            <td style="padding:12px 8px; color:#64748b; font-size:0.8em;">{sample['source']}</td>
        </tr>
        """

    # ── Expanded detail rows (answer + context) ──────────────────────────
    detail_cards = ""
    for i, sample in enumerate(per_sample):
        scores = sample.get("scores", {})
        detail_cards += f"""
        <details style="background:#1e293b; border-radius:8px; margin-bottom:8px; padding:0;">
            <summary style="padding:12px 16px; cursor:pointer; color:#e2e8f0; font-size:0.9em;">
                <strong>#{i+1}</strong> — {sample['question']}
                &nbsp;&nbsp; {_score_badge(scores.get('faithfulness'))}
                {_score_badge(scores.get('answer_relevancy'))}
            </summary>
            <div style="padding:0 16px 16px 16px;">
                <div style="margin-bottom:12px;">
                    <div style="font-size:0.75em; color:#94a3b8; margin-bottom:4px;">Generated Answer</div>
                    <div style="background:#0f172a; padding:10px 12px; border-radius:6px; color:#cbd5e1; font-size:0.85em; line-height:1.5;">
                        {sample['answer']}
                    </div>
                </div>
                <div style="margin-bottom:12px;">
                    <div style="font-size:0.75em; color:#94a3b8; margin-bottom:4px;">Retrieved Context (snippet)</div>
                    <div style="background:#0f172a; padding:10px 12px; border-radius:6px; color:#64748b; font-size:0.85em; line-height:1.5;">
                        {sample['context_snippet']}
                    </div>
                </div>
                <div>
                    <div style="font-size:0.75em; color:#94a3b8; margin-bottom:4px;">Ground Truth (snippet)</div>
                    <div style="background:#0f172a; padding:10px 12px; border-radius:6px; color:#64748b; font-size:0.85em; line-height:1.5;">
                        {sample['ground_truth_snippet']}
                    </div>
                </div>
            </div>
        </details>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Travelo AI — RAG Evaluation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 12px 8px; color: #94a3b8; font-size: 0.8em;
              font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
              border-bottom: 2px solid #1e293b; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div style="margin-bottom:40px;">
            <h1 style="font-size:1.8em; font-weight:700; margin-bottom:4px;">
                🧭 Travelo AI — RAG Evaluation Report
            </h1>
            <p style="color:#64748b; font-size:0.9em;">
                Generated: {metadata['timestamp']} &nbsp;|&nbsp;
                Samples: {metadata['num_samples']} &nbsp;|&nbsp;
                Duration: {metadata['elapsed_seconds']}s &nbsp;|&nbsp;
                Threshold: {metadata['chroma_similarity_threshold']}
            </p>
            <p style="color:#475569; font-size:0.8em; margin-top:4px;">
                Generation: {metadata['llm_model']} &nbsp;|&nbsp;
                Embeddings: {metadata['embedding_model']}
            </p>
        </div>

        <!-- Aggregate Metrics -->
        <h2 style="font-size:1.1em; color:#94a3b8; margin-bottom:16px; font-weight:600;">
            Aggregate Scores
        </h2>
        <div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:40px;">
            {metric_cards}
        </div>

        <!-- Per-Sample Table -->
        <h2 style="font-size:1.1em; color:#94a3b8; margin-bottom:16px; font-weight:600;">
            Per-Sample Scores
        </h2>
        <div style="overflow-x:auto; margin-bottom:40px;">
            <table>
                <thead>
                    <tr>
                        <th>Place</th>
                        <th>Question</th>
                        <th>Faithfulness</th>
                        <th>Relevancy</th>
                        <th>Ctx Precision</th>
                        <th>Ctx Recall</th>
                        <th>Source</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <!-- Detailed Expandable Rows -->
        <h2 style="font-size:1.1em; color:#94a3b8; margin-bottom:16px; font-weight:600;">
            Detailed Results (click to expand)
        </h2>
        {detail_cards}

        <!-- Footer -->
        <div style="margin-top:48px; padding-top:16px; border-top:1px solid #1e293b;
                     color:#475569; font-size:0.75em; text-align:center;">
            Travelo AI RAG Evaluation Framework &nbsp;·&nbsp; Powered by RAGAS + Gemini
        </div>
    </div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
