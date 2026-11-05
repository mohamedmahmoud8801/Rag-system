"""
RAGAS evaluator for the mini-rag project.

Run from the src/ folder:

    PYTHONPATH=. python evaluation/ragas_evaluator.py --ids Q01 --tag test
    PYTHONPATH=. python evaluation/ragas_evaluator.py --tag full
    PYTHONPATH=. python evaluation/ragas_evaluator.py --category "Multi-hop"
    PYTHONPATH=. python evaluation/ragas_evaluator.py --limit 5
    PYTHONPATH=. python evaluation/ragas_evaluator.py --metrics faithfulness,context_recall
    PYTHONPATH=. python evaluation/ragas_evaluator.py --atomic      # extra slow diagnostic

Environment variables:
    RAGAS_JUDGE_MODEL  (default: qwen2.5:7b-instruct)
    RAGAS_JUDGE_URL    (default: http://localhost:11434/v1)
"""

import argparse
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from datasets import Dataset
from openai import OpenAI
from ragas import evaluate
from ragas.llms import llm_factory
from ragas.metrics import ContextPrecision, ContextRecall, Faithfulness
from ragas.run_config import RunConfig
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from controllers.NLPController import NLPController
from helpers.config import get_settings
from models.AssetModel import AssetModel
from models.ProjectModel import ProjectModel
from models.enums.AssetTypeEnum import AssetTypeEnum
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from stores.reranker.RerankerProviderFactory import RerankerProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory


# ==========================================================================
# Config
# ==========================================================================

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = EVAL_DIR / "datasets" / "rag_golden_questions_42.json"
RESULTS_DIR = EVAL_DIR / "results"

JUDGE_MODEL = os.getenv("RAGAS_JUDGE_MODEL", "qwen2.5:7b-instruct")
JUDGE_URL = os.getenv("RAGAS_JUDGE_URL", "http://localhost:11434/v1")

CALL_TIMEOUT = 3600.0   # per judge HTTP call
JOB_TIMEOUT = 7200      # per RAGAS job
RETRIEVAL_LIMIT = 10
TARGET_PDF = "NIPS-2017-attention-is-all-you-need-Paper.pdf"

METRIC_CLASSES = {
    "faithfulness": Faithfulness,
    "context_precision": ContextPrecision,
    "context_recall": ContextRecall,
}


# ==========================================================================
# RAG components
# ==========================================================================

async def build_rag_components():
    s = get_settings()

    db_engine = create_async_engine(
        f"postgresql+asyncpg://{s.POSTGRES_USERNAME}:{s.POSTGRES_PASSWORD}"
        f"@{s.POSTGRES_HOST}:{s.POSTGRES_PORT}/{s.POSTGRES_MAIN_DATABASE}"
    )
    db_client = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    llm_factory_project = LLMProviderFactory(s)

    generation_client = llm_factory_project.create(provider=s.GENERATION_BACKEND)
    generation_client.set_generation_model(model_id=s.GENERATION_MODEL_ID)

    embedding_client = llm_factory_project.create(provider=s.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(
        model_id=s.EMBEDDING_MODEL_ID,
        embedding_size=s.EMBEDDING_MODEL_SIZE,
    )

    vectordb_client = VectorDBProviderFactory(
        config=s, db_client=db_client
    ).create(provider=s.VECTOR_DB_BACKEND)
    await vectordb_client.connect()

    reranker_client = RerankerProviderFactory.create(
        provider=s.RERANKER_PROVIDER,
        model_id=s.RERANKER_MODEL_ID,
    )

    template_parser = TemplateParser(
        language=s.PRIMARY_LANG,
        default_language=s.DEFAULT_LANG,
    )

    nlp_controller = NLPController(
        vectordb_client=vectordb_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        reranker_client=reranker_client,
        template_parser=template_parser,
    )

    project_model = await ProjectModel.create_instance(db_client=db_client)
    project = await project_model.get_project_or_create_one(project_id=1)

    return nlp_controller, project, db_engine, db_client, vectordb_client


async def resolve_file_id(db_client, file_id):
    """Return file_id as given, or find the evaluation PDF automatically."""
    if file_id:
        return file_id

    asset_model = await AssetModel.create_instance(db_client=db_client)
    assets = await asset_model.get_all_project_assets(
        asset_project_id=1,
        asset_type=AssetTypeEnum.FILE.value,
    )

    target = TARGET_PDF.lower()
    matches = [
        a for a in assets
        if (a.asset_config or {}).get("original_filename", "")
        .lower().replace("_", "-") == target
    ]

    if len(matches) != 1:
        available = [
            (a.asset_config or {}).get("original_filename") or a.asset_name
            for a in assets
        ]
        raise RuntimeError(
            f"Could not uniquely identify the evaluation PDF. "
            f"Matches: {len(matches)}. Available files: {available}"
        )

    return matches[0].asset_name


# ==========================================================================
# Dataset helpers
# ==========================================================================

def load_questions(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Golden dataset must be a non-empty JSON list.")

    items = []
    for i, row in enumerate(data, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Record {i} is not an object.")

        question = str(row.get("question", "")).strip()
        truth = str(row.get("ground_truth", "")).strip()

        if "id" not in row or not question or not truth:
            raise ValueError(
                f"Record {i} needs a non-empty id, question and ground_truth."
            )

        items.append({
            "id": row["id"],
            "category": row.get("category", ""),
            "question": question,
            "ground_truth": truth,
            "source_section": row.get("source_section", ""),
            "needs_multiple_chunks": row.get("needs_multiple_chunks", False),
        })

    return items


def normalize_contexts(contexts):
    """Make sure retrieved_contexts is a list of non-empty plain strings."""
    out = []
    for c in contexts or []:
        value = c.get("text", c) if isinstance(c, dict) else getattr(c, "text", c)
        text = str(value).strip()
        if text:
            out.append(text)
    return out


# ==========================================================================
# Judge
# ==========================================================================

def build_judge_client():
    return OpenAI(
        base_url=JUDGE_URL,
        api_key="ollama",
        timeout=httpx.Timeout(CALL_TIMEOUT, connect=10.0),
        max_retries=0,
    )


ATOMIC_SYSTEM_PROMPT = """
You are a strict retrieval-evaluation judge.

Measure how much of a reference answer is supported by the retrieved contexts.

Rules:
1. Decompose the reference into the smallest meaningful, independently
   verifiable factual claims. Preserve all factual details.
2. Split lists of people, entities, numbers and properties into
   independent claims. Do not split a person's name into tokens.
3. Do not use outside knowledge. Evaluate every claim independently.
4. A claim is supported only if the contexts explicitly provide
   sufficient evidence.
5. For each supported claim give a short quote copied verbatim from a
   retrieved context. The quote itself must contain the needed
   information (an email address alone does not prove a full name).
6. Never invent or paraphrase a quote. If there is no sufficient
   evidence, mark the claim false and use an empty evidence string.

Return only a valid JSON object:
{
  "claims": [
    {
      "claim": "An independently verifiable factual claim",
      "supported": true,
      "evidence": "Exact quote from a retrieved context",
      "reason": "Why the quote supports the claim"
    }
  ]
}
"""


def atomic_context_recall(client, question, reference, contexts):
    """
    Optional diagnostic: share of atomic reference claims supported by the
    contexts. A claim counts only if the judge's evidence quote is found
    verbatim in one of the contexts. One judge call per question.
    """

    def norm(text):
        return re.sub(r"\s+", " ", str(text or "").casefold()).strip()

    def failed(error):
        return {"score": None, "supported_claims": 0, "total_claims": 0,
                "claims": [], "error": error}

    if not contexts:
        return failed("No retrieved contexts.")

    normalized = [norm(c) for c in contexts]
    context_text = "\n\n".join(
        f"[Context {i}]\n{c}" for i, c in enumerate(contexts, start=1)
    )

    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Reference answer:\n{reference}\n\n"
        f"Retrieved contexts:\n{context_text}\n\n"
        "Decompose the reference into atomic factual claims. Evaluate each "
        "claim using only the retrieved contexts, with an exact quote for "
        "every supported claim."
    )

    try:
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": ATOMIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        claims = json.loads(response.choices[0].message.content or "").get("claims")
        if not isinstance(claims, list):
            raise ValueError("Judge response has no valid 'claims' list.")
    except Exception as exc:
        return failed(f"{type(exc).__name__}: {exc}")

    valid = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        claim_text = str(c.get("claim", "")).strip()
        judge_supported = c.get("supported")
        if not claim_text or not isinstance(judge_supported, bool):
            continue

        evidence = str(c.get("evidence", "")).strip()
        verified = (
            judge_supported
            and bool(norm(evidence))
            and any(norm(evidence) in ctx for ctx in normalized)
        )
        valid.append({
            "claim": claim_text,
            "supported": verified,
            "judge_supported": judge_supported,
            "evidence": evidence,
            "reason": str(c.get("reason", "")).strip(),
        })

    total = len(valid)
    supported = sum(c["supported"] for c in valid)

    return {
        "score": supported / total if total else None,
        "supported_claims": supported,
        "total_claims": total,
        "claims": valid,
        "error": None if total else "Judge returned no valid atomic claims.",
    }


# ==========================================================================
# Main
# ==========================================================================

async def main(args):

    # Fail fast on bad arguments, before loading any model.
    wanted_metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    unknown = set(wanted_metrics) - set(METRIC_CLASSES)
    if unknown or not wanted_metrics:
        raise ValueError(
            f"Unknown metrics: {sorted(unknown)}. "
            f"Choose from: {sorted(METRIC_CLASSES)}"
        )

    json_path = Path(args.json) if args.json else DEFAULT_DATASET
    tag = args.tag or "golden"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    (
        nlp_controller,
        project,
        db_engine,
        db_client,
        vectordb_client,
    ) = await build_rag_components()

    try:
        file_id = await resolve_file_id(db_client, args.file_id)

        # ------------------------------------------------------------------
        # Questions
        # ------------------------------------------------------------------
        questions = load_questions(json_path)
        total_loaded = len(questions)

        if args.ids:
            wanted_ids = {x.strip() for x in args.ids.split(",") if x.strip()}
            questions = [q for q in questions if str(q["id"]) in wanted_ids]

        if args.category:
            questions = [q for q in questions if q["category"] == args.category]

        if args.limit:
            questions = questions[:args.limit]

        if not questions:
            raise RuntimeError(
                "No questions matched the filters (--ids / --category / --limit)."
            )

        print("=" * 80)
        print(f"RAGAS EVALUATION | tag={tag}")
        print(f"File      : {file_id}")
        print(f"Dataset   : {json_path} ({total_loaded} loaded, {len(questions)} selected)")
        print(f"Judge     : {JUDGE_MODEL}")
        print(f"Metrics   : {', '.join(wanted_metrics)}"
              f"{' + atomic recall' if args.atomic else ''}")
        print("=" * 80)

        # ------------------------------------------------------------------
        # RAG: answer every question
        # ------------------------------------------------------------------
        rows, extras, failed_questions = [], [], []
        checkpoint_path = RESULTS_DIR / f"checkpoint_{tag}_{stamp}.jsonl"

        for index, item in enumerate(questions, start=1):
            print(
                f"[{index}/{len(questions)}] {item['id']} | "
                f"{item['category']} | {item['question']}"
            )
            started = time.time()

            try:
                result = await nlp_controller.answer_rag_question(
                    project=project,
                    query=item["question"],
                    limit=RETRIEVAL_LIMIT,
                    return_contexts=True,
                    file_id=file_id,
                    db_client=db_client,
                )

                if not isinstance(result, tuple) or len(result) != 5:
                    raise RuntimeError(
                        "Unexpected answer_rag_question result: "
                        f"{type(result).__name__}"
                    )

                answer, _, _, contexts, _ = result
                answer = str(answer).strip() if answer is not None else ""
                contexts = normalize_contexts(contexts)
                elapsed = time.time() - started

                problems = []
                if not answer:
                    problems.append("answer is empty")
                if not contexts:
                    problems.append("retrieved_contexts is empty")
                if problems:
                    raise RuntimeError("; ".join(problems))

                print(f"    {len(contexts)} contexts | {elapsed:.0f}s | {answer[:200]}")

                row = {
                    "user_input": item["question"],
                    "response": answer,
                    "retrieved_contexts": contexts,
                    "reference": item["ground_truth"],
                }
                extra = {
                    "id": item["id"],
                    "category": item["category"],
                    "source_section": item["source_section"],
                    "needs_multiple_chunks": item["needs_multiple_chunks"],
                    "rag_seconds": round(elapsed, 1),
                }
                rows.append(row)
                extras.append(extra)

                with open(checkpoint_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({**row, **extra}, ensure_ascii=False) + "\n")

            except Exception as exc:
                print(f"    FAILED: {exc!r}")
                failed_questions.append({
                    "id": item["id"],
                    "question": item["question"],
                    "reason": repr(exc),
                })

        print()
        print(f"RAG done: {len(rows)}/{len(questions)} ok, "
              f"{len(failed_questions)} failed")

        if not rows:
            raise RuntimeError("No valid RAG rows were generated. RAGAS was not started.")

        # ------------------------------------------------------------------
        # RAGAS
        # ------------------------------------------------------------------
        judge_client = build_judge_client()
        ragas_llm = llm_factory(
            model=JUDGE_MODEL,
            provider="openai",
            client=judge_client,
            temperature=0.0,
        )

        metrics = [METRIC_CLASSES[m](llm=ragas_llm) for m in wanted_metrics]

        print("=" * 80)
        print("STARTING RAGAS EVALUATION")
        print("=" * 80)

        eval_started = time.time()
        result = evaluate(
            dataset=Dataset.from_list(rows),
            metrics=metrics,
            llm=ragas_llm,
            run_config=RunConfig(
                timeout=JOB_TIMEOUT,
                max_retries=2,
                max_workers=args.workers,
            ),
            raise_exceptions=False,
            show_progress=True,
        )
        eval_minutes = (time.time() - eval_started) / 60

        print()
        print(result)
        print(f"Evaluation time: {eval_minutes:.1f} min")

        df = result.to_pandas()

        for key in ("id", "category", "source_section",
                    "needs_multiple_chunks", "rag_seconds"):
            df[key] = [extra[key] for extra in extras]

        # ------------------------------------------------------------------
        # Optional: atomic context recall (slow, extra judge call per question)
        # ------------------------------------------------------------------
        atomic_results = []

        if args.atomic:
            print()
            print("ATOMIC CONTEXT RECALL")

            for index, row in enumerate(rows, start=1):
                atomic = atomic_context_recall(
                    client=judge_client,
                    question=row["user_input"],
                    reference=row["reference"],
                    contexts=row["retrieved_contexts"],
                )
                atomic_results.append(atomic)

                if atomic["score"] is None:
                    print(f"[{index}/{len(rows)}] unavailable: {atomic['error']}")
                else:
                    print(
                        f"[{index}/{len(rows)}] {atomic['score']:.4f} "
                        f"({atomic['supported_claims']}/{atomic['total_claims']} claims)"
                    )

            df["atomic_context_recall"] = [a["score"] for a in atomic_results]
            df["atomic_supported_claims"] = [a["supported_claims"] for a in atomic_results]
            df["atomic_total_claims"] = [a["total_claims"] for a in atomic_results]
            df["atomic_claim_details"] = [
                json.dumps(a["claims"], ensure_ascii=False) for a in atomic_results
            ]
            df["atomic_recall_error"] = [a["error"] or "" for a in atomic_results]

        # ------------------------------------------------------------------
        # Report
        # ------------------------------------------------------------------
        score_cols = [
            c for c in (*wanted_metrics, "atomic_context_recall")
            if c in df.columns
        ]

        print()
        print("Per-question scores:")
        print(df[["id", "category"] + score_cols].to_string(index=False))

        if df["category"].nunique() > 1:
            print()
            print("Average per category:")
            print(df.groupby("category")[score_cols].mean().round(3).to_string())

        print()
        print("Overall average:")
        print(df[score_cols].mean().round(4).to_string())

        nan_counts = df[score_cols].isna().sum()
        print()
        print("NaN per metric (failed/timed-out jobs):")
        print(nan_counts.to_string())
        if nan_counts.sum() > 0:
            print(
                "WARNING: some RAGAS jobs failed. Do not trust the "
                "corresponding averages until NaN = 0."
            )

        # ------------------------------------------------------------------
        # Save
        # ------------------------------------------------------------------
        base = RESULTS_DIR / f"ragas_{tag}_{stamp}"

        df.to_csv(f"{base}.csv", index=False, encoding="utf-8-sig")

        with open(f"{base}_rows.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

        with open(f"{base}_failed.json", "w", encoding="utf-8") as f:
            json.dump(failed_questions, f, ensure_ascii=False, indent=2)

        print()
        print(f"Saved scores : {base}.csv")
        print(f"Saved rows   : {base}_rows.json")
        print(f"Saved failed : {base}_failed.json")

        if atomic_results:
            with open(f"{base}_atomic_claims.json", "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "id": extra["id"],
                            "question": row["user_input"],
                            "reference": row["reference"],
                            **atomic,
                        }
                        for row, extra, atomic in zip(rows, extras, atomic_results)
                    ],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"Saved atomic : {base}_atomic_claims.json")

    finally:
        await vectordb_client.disconnect()
        await db_engine.dispose()


# ==========================================================================
# CLI
# ==========================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="RAGAS evaluation for mini-rag using the golden dataset."
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="Evaluate only the first N questions. 0 = all.")
    parser.add_argument("--file-id", default="",
                        help="Internal file_id of the indexed PDF (auto-resolved if omitted).")
    parser.add_argument("--json", default="",
                        help="Path to the golden dataset JSON.")
    parser.add_argument("--tag", default="", help="Label for this run.")
    parser.add_argument("--ids", default="",
                        help="Comma-separated question ids, e.g. Q04,Q13,Q19.")
    parser.add_argument("--category", default="",
                        help='Only one category, e.g. Factual or "Multi-hop".')
    parser.add_argument("--metrics",
                        default="faithfulness,context_precision,context_recall",
                        help="Comma-separated RAGAS metrics to run.")
    parser.add_argument("--atomic", action="store_true",
                        help="Also run the slow atomic context recall diagnostic.")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel RAGAS jobs (keep 1 on CPU-only Ollama).")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))