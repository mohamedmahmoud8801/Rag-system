"""
RAGAS evaluator for the mini-rag project.

Run examples (from the src/ folder):

    # quick smoke test: first question only
    PYTHONPATH=. python evaluation/ragas_evaluator.py --limit 1

    # evaluate all 42 golden questions
    PYTHONPATH=. python evaluation/ragas_evaluator.py

    # evaluate specific questions by id
    PYTHONPATH=. python evaluation/ragas_evaluator.py \
        --ids Q04,Q05,Q13,Q19,Q25,Q31 --tag smoke

    # evaluate one category only
    PYTHONPATH=. python evaluation/ragas_evaluator.py \
        --category "Multi-hop" --tag multihop

    # explicitly specify the JSON dataset
    PYTHONPATH=. python evaluation/ragas_evaluator.py \
        --json evaluation/datasets/rag_golden_questions_42.json

    # evaluate a different indexed PDF
    PYTHONPATH=. python evaluation/ragas_evaluator.py \
        --file-id <file_id>

Optional environment variables:

    RAGAS_JUDGE_MODEL
        Judge model served by Ollama.
        Default: qwen2.5:7b-instruct

    RAGAS_JUDGE_URL
        Ollama OpenAI-compatible URL.
        Default: http://localhost:11434/v1
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from datasets import Dataset
from openai import OpenAI
from ragas import evaluate
from ragas.llms import llm_factory
from ragas.metrics import (
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from ragas.run_config import RunConfig

from controllers.NLPController import NLPController
from helpers.config import get_settings
from models.ProjectModel import ProjectModel
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.reranker.RerankerProviderFactory import (
    RerankerProviderFactory,
)
from stores.vectordb.VectorDBProviderFactory import (
    VectorDBProviderFactory,
)
from stores.llm.templates.template_parser import TemplateParser


# ==========================================================================
# Paths / Settings
# ==========================================================================

EVALUATION_DIR = Path(__file__).resolve().parent

DEFAULT_DATASET = (
    EVALUATION_DIR
    / "datasets"
    / "rag_golden_questions_42.json"
)

# NOTE: must match the asset name stored in the `assets` table exactly
# ("allyouneed", not "allyyouneed").
DEFAULT_FILE_ID = (
    "3dcnox5etx82_NIPS2017attentionisallyouneedPaper.pdf"
)


# ==========================================================================
# RAGAS judge
# ==========================================================================

JUDGE_MODEL = os.getenv(
    "RAGAS_JUDGE_MODEL",
    "qwen2.5:7b-instruct",
)

JUDGE_URL = os.getenv(
    "RAGAS_JUDGE_URL",
    "http://localhost:11434/v1",
)


# ==========================================================================
# Timeouts
# ==========================================================================

CALL_TIMEOUT = 3600.0
JOB_TIMEOUT = 7200


# ==========================================================================
# RAG settings
# ==========================================================================

RETRIEVAL_LIMIT = 10

GEN_RETRIES = 1

GEN_TIMEOUT = 3700


# ==========================================================================
# Results
# ==========================================================================

RESULTS_DIR = (
    EVALUATION_DIR
    / "results"
)


# ==========================================================================
# Build RAG components
# ==========================================================================

async def build_rag_components():

    settings = get_settings()

    # ----------------------------------------------------------------------
    # PostgreSQL
    # ----------------------------------------------------------------------

    postgres_conn = (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USERNAME}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DATABASE}"
    )

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
    )
    from sqlalchemy.orm import sessionmaker

    db_engine = create_async_engine(
        postgres_conn
    )

    db_client = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # ----------------------------------------------------------------------
    # LLM
    # ----------------------------------------------------------------------

    llm_factory_project = LLMProviderFactory(
        settings
    )

    generation_client = llm_factory_project.create(
        provider=settings.GENERATION_BACKEND
    )

    generation_client.set_generation_model(
        model_id=settings.GENERATION_MODEL_ID
    )

    # ----------------------------------------------------------------------
    # Embedding
    # ----------------------------------------------------------------------

    embedding_client = llm_factory_project.create(
        provider=settings.EMBEDDING_BACKEND
    )

    embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE,
    )

    # ----------------------------------------------------------------------
    # Vector DB
    # ----------------------------------------------------------------------

    vectordb_factory = VectorDBProviderFactory(
        config=settings,
        db_client=db_client,
    )

    vectordb_client = vectordb_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )

    await vectordb_client.connect()

    # ----------------------------------------------------------------------
    # Reranker
    # ----------------------------------------------------------------------

    reranker_client = RerankerProviderFactory.create(
        provider=settings.RERANKER_PROVIDER,
        model_id=settings.RERANKER_MODEL_ID,
    )

    # ----------------------------------------------------------------------
    # Template parser
    # ----------------------------------------------------------------------

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

    # ----------------------------------------------------------------------
    # NLP Controller
    # ----------------------------------------------------------------------

    nlp_controller = NLPController(
        vectordb_client=vectordb_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        reranker_client=reranker_client,
        template_parser=template_parser,
    )

    # ----------------------------------------------------------------------
    # Project
    # ----------------------------------------------------------------------

    project_model = await ProjectModel.create_instance(
        db_client=db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=1
    )

    return (
        nlp_controller,
        project,
        db_engine,
        db_client,
        vectordb_client,
    )


# ==========================================================================
# Golden dataset
# ==========================================================================

def load_questions_from_json(json_path):
    """
    Load the RAG golden-set JSON.

    Required fields:

        id
        question
        ground_truth

    Optional metadata:

        category
        reference
        source_section
        needs_multiple_chunks
        note
    """

    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(
            f"Golden dataset not found:\n{json_path}"
        )

    with open(
        json_path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "Golden dataset JSON must contain "
            "a list of question objects."
        )

    required_fields = {
        "id",
        "question",
        "ground_truth",
    }

    items = []

    for index, row in enumerate(
        data,
        start=1,
    ):

        if not isinstance(row, dict):
            raise ValueError(
                f"Invalid record at JSON index {index}. "
                "Each record must be an object."
            )

        missing_fields = (
            required_fields
            - set(row.keys())
        )

        if missing_fields:
            raise ValueError(
                f"Record {index} is missing "
                f"required fields: "
                f"{sorted(missing_fields)}"
            )

        question = str(
            row.get("question", "")
        ).strip()

        ground_truth = str(
            row.get("ground_truth", "")
        ).strip()

        if not question:
            raise ValueError(
                f"Record {index} has an empty question."
            )

        if not ground_truth:
            raise ValueError(
                f"Record {index} has an empty ground_truth."
            )

        items.append(
            {
                "id": row["id"],
                "category": row.get(
                    "category",
                    "",
                ),
                "question": question,
                "ground_truth": ground_truth,
                "reference": row.get(
                    "reference",
                    "",
                ),
                "source_section": row.get(
                    "source_section",
                    "",
                ),
                "needs_multiple_chunks": row.get(
                    "needs_multiple_chunks",
                    False,
                ),
                "note": row.get(
                    "note",
                    "",
                ),
            }
        )

    if not items:
        raise ValueError(
            f"No questions found in:\n{json_path}"
        )

    return items


# ==========================================================================
# Context normalization
# ==========================================================================

def normalize_contexts(contexts):
    """
    Make sure retrieved_contexts is a list of plain strings.
    """

    out = []

    for context in contexts or []:

        if isinstance(context, str):

            text = context.strip()

            if text:
                out.append(text)

        elif isinstance(context, dict):

            value = context.get(
                "text",
                context,
            )

            text = str(value).strip()

            if text:
                out.append(text)

        else:

            value = getattr(
                context,
                "text",
                context,
            )

            text = str(value).strip()

            if text:
                out.append(text)

    return out


# ==========================================================================
# RAG result validation
# ==========================================================================

def validate_rag_result(
    answer,
    contexts,
):
    """
    Validate that the RAG pipeline actually returned
    usable output before sending it to RAGAS.

    RAGAS should never receive a fake/empty RAG result.
    """

    problems = []

    if not isinstance(answer, str):
        problems.append(
            f"answer has unexpected type: "
            f"{type(answer).__name__}"
        )

    if not answer or not answer.strip():
        problems.append(
            "answer is empty"
        )

    if not contexts:
        problems.append(
            "retrieved_contexts is empty"
        )

    return problems


# ==========================================================================
# RAGAS judge
# ==========================================================================

def build_ragas_llm():

    client = OpenAI(
        base_url=JUDGE_URL,
        api_key="ollama",
        timeout=httpx.Timeout(
            CALL_TIMEOUT,
            connect=10.0,
        ),
        max_retries=0,
    )

    return llm_factory(
        model=JUDGE_MODEL,
        provider="openai",
        client=client,
        temperature=0.0,
    )


# ==========================================================================
# Main
# ==========================================================================

async def main(args):

    # ----------------------------------------------------------------------
    # Resolve dataset
    # ----------------------------------------------------------------------

    json_path = (
        Path(args.json)
        if args.json
        else DEFAULT_DATASET
    )

    file_id = args.file_id

    # ----------------------------------------------------------------------
    # Header
    # ----------------------------------------------------------------------

    print("=" * 80)
    print("RAGAS EVALUATION")
    print("=" * 80)

    print(
        f"Evaluation file : {file_id}"
    )

    print(
        f"Golden dataset  : {json_path}"
    )

    print(
        f"Judge model     : {JUDGE_MODEL}"
    )

    print(
        f"Call timeout    : "
        f"{CALL_TIMEOUT}s | "
        f"Job timeout: {JOB_TIMEOUT}s"
    )

    print()

    # ----------------------------------------------------------------------
    # Build RAG components
    # ----------------------------------------------------------------------

    (
        nlp_controller,
        project,
        db_engine,
        db_client,
        vectordb_client,
    ) = await build_rag_components()

    try:

        # ------------------------------------------------------------------
        # Load golden questions
        # ------------------------------------------------------------------

        questions = load_questions_from_json(
            json_path
        )

        print(
            f"Golden questions loaded: "
            f"{len(questions)}"
        )

        # ------------------------------------------------------------------
        # Optional filters: --ids and --category
        # ------------------------------------------------------------------

        if args.ids:

            wanted_ids = {
                x.strip()
                for x in args.ids.split(",")
                if x.strip()
            }

            questions = [
                q
                for q in questions
                if str(q["id"]) in wanted_ids
            ]

        if args.category:

            questions = [
                q
                for q in questions
                if q["category"] == args.category
            ]

        # ------------------------------------------------------------------
        # Optional limit
        # ------------------------------------------------------------------

        if args.limit:
            questions = questions[
                :args.limit
            ]

        print(
            f"Questions to evaluate: "
            f"{len(questions)}"
        )

        print()

        if not questions:

            raise RuntimeError(
                "No questions matched the filters "
                "(--ids / --category / --limit). "
                "Check the spelling of the ids or the "
                "category name."
            )

        # ------------------------------------------------------------------
        # RAG rows
        # ------------------------------------------------------------------

        rows = []

        extras = []

        failed_questions = []

        # ------------------------------------------------------------------
        # Evaluate each question through RAG
        # ------------------------------------------------------------------

        for index, item in enumerate(
            questions,
            start=1,
        ):

            question = item["question"]

            print("-" * 80)

            print(
                f"Question "
                f"{index}/{len(questions)}"
            )

            print(
                f"ID: "
                f"{item.get('id', index)}"
            )

            print(
                f"Category: "
                f"{item.get('category', '')}"
            )

            print(
                f"Source section: "
                f"{item.get('source_section', '')}"
            )

            print(
                "Needs multiple chunks: "
                f"{item.get('needs_multiple_chunks', False)}"
            )

            print(
                f"Question: {question}"
            )

            started = time.time()

            try:

                # ----------------------------------------------------------
                # RAG generation
                # ----------------------------------------------------------

                result = None

                for attempt in range(
                    1,
                    GEN_RETRIES + 2,
                ):

                    try:

                        result = await asyncio.wait_for(

                            nlp_controller.answer_rag_question(
                                project=project,
                                query=question,
                                limit=RETRIEVAL_LIMIT,
                                return_contexts=True,
                                file_id=file_id,
                            ),

                            timeout=GEN_TIMEOUT,
                        )

                        break

                    except Exception as exc:

                        print(
                            f"Attempt "
                            f"{attempt}/"
                            f"{GEN_RETRIES + 1} "
                            f"failed: {exc!r}"
                        )

                        if (
                            attempt
                            == GEN_RETRIES + 1
                        ):
                            raise

                # ----------------------------------------------------------
                # IMPORTANT DIAGNOSTIC
                # ----------------------------------------------------------

                print(
                    f"RAG result type: "
                    f"{type(result).__name__}"
                )

                if isinstance(result, tuple):

                    print(
                        f"RAG result length: "
                        f"{len(result)}"
                    )

                print(
                    f"RAG raw result: "
                    f"{result!r}"
                )

                # ----------------------------------------------------------
                # Validate expected project contract
                #
                # Current NLPController contract:
                #
                #     answer, _, _, contexts
                # ----------------------------------------------------------

                if not isinstance(result, tuple):

                    raise RuntimeError(
                        "Unexpected answer_rag_question "
                        "return type. Expected tuple, "
                        f"got {type(result).__name__}."
                    )

                if len(result) < 4:

                    raise RuntimeError(
                        "Unexpected answer_rag_question "
                        "return length. Expected at "
                        f"least 4 values, got {len(result)}."
                    )

                (
                    answer,
                    _,
                    _,
                    contexts,
                ) = result

                # ----------------------------------------------------------
                # Normalize
                # ----------------------------------------------------------

                if isinstance(answer, str):
                    answer = answer.strip()
                elif answer is None:
                    answer = ""
                else:
                    answer = str(answer).strip()

                contexts = normalize_contexts(
                    contexts
                )

                elapsed = (
                    time.time()
                    - started
                )

                # ----------------------------------------------------------
                # Validate RAG output
                # ----------------------------------------------------------

                problems = validate_rag_result(
                    answer,
                    contexts,
                )

                print(
                    f"Generated answer: "
                    f"{bool(answer)}"
                )

                print(
                    "Answer "
                    "(first 300 chars): "
                    f"{answer[:300]}"
                )

                print(
                    f"Retrieved contexts: "
                    f"{len(contexts)}"
                )

                print(
                    f"RAG time: "
                    f"{elapsed:.1f}s"
                )

                # ----------------------------------------------------------
                # DO NOT send broken RAG results to RAGAS
                # ----------------------------------------------------------

                if problems:

                    failure_reason = (
                        "; ".join(problems)
                    )

                    print()
                    print(
                        "RAG OUTPUT INVALID:"
                    )
                    print(
                        f"  {failure_reason}"
                    )

                    failed_questions.append(
                        {
                            "id": item.get(
                                "id",
                                index,
                            ),
                            "question": question,
                            "reason": failure_reason,
                            "raw_result": repr(result),
                        }
                    )

                    continue

                # ----------------------------------------------------------
                # RAGAS row
                # ----------------------------------------------------------

                ragas_row = {
                    "user_input": question,
                    "response": answer,
                    "retrieved_contexts": contexts,
                    "reference": item[
                        "ground_truth"
                    ],
                }

                rows.append(
                    ragas_row
                )

                # ----------------------------------------------------------
                # Metadata
                # ----------------------------------------------------------

                extra_row = {
                    "id": item.get(
                        "id",
                        index,
                    ),
                    "category": item.get(
                        "category",
                        "",
                    ),
                    "source_section": item.get(
                        "source_section",
                        "",
                    ),
                    "needs_multiple_chunks": item.get(
                        "needs_multiple_chunks",
                        False,
                    ),
                    "rag_seconds": round(
                        elapsed,
                        1,
                    ),
                }

                extras.append(
                    extra_row
                )

                # ----------------------------------------------------------
                # Checkpoint
                # ----------------------------------------------------------

                RESULTS_DIR.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                checkpoint_path = (
                    RESULTS_DIR
                    / "checkpoint_rows.jsonl"
                )

                with open(
                    checkpoint_path,
                    "a",
                    encoding="utf-8",
                ) as f:

                    f.write(
                        json.dumps(
                            {
                                **ragas_row,
                                **extra_row,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

            except Exception as exc:

                print(
                    f"RAG generation failed: "
                    f"{exc!r}"
                )

                failed_questions.append(
                    {
                        "id": item.get(
                            "id",
                            index,
                        ),
                        "question": question,
                        "reason": repr(exc),
                    }
                )

        # ----------------------------------------------------------------------
        # Summary of RAG generation
        # ----------------------------------------------------------------------

        print()
        print("=" * 80)
        print("RAG GENERATION SUMMARY")
        print("=" * 80)

        print(
            f"Successful RAG rows : "
            f"{len(rows)}/{len(questions)}"
        )

        print(
            f"Failed RAG questions: "
            f"{len(failed_questions)}/{len(questions)}"
        )

        if failed_questions:

            print()
            print(
                "Failed questions:"
            )

            for failed in failed_questions:

                print(
                    f"- {failed['id']}: "
                    f"{failed['reason']}"
                )

        # ----------------------------------------------------------------------
        # Make sure at least one row succeeded
        # ----------------------------------------------------------------------

        if not rows:

            raise RuntimeError(
                "No valid RAG rows were generated. "
                "RAGAS was not started. "
                "Inspect the RAG raw result above."
            )

        # ----------------------------------------------------------------------
        # Build HuggingFace Dataset
        # ----------------------------------------------------------------------

        dataset = Dataset.from_list(
            rows
        )

        print()
        print("=" * 80)
        print("RAGAS DATASET READY")
        print("=" * 80)

        print(
            f"Rows successfully generated: "
            f"{len(rows)}/{len(questions)}"
        )

        print()

        # ----------------------------------------------------------------------
        # Build RAGAS judge
        # ----------------------------------------------------------------------

        ragas_llm = build_ragas_llm()

        # ----------------------------------------------------------------------
        # RAGAS run configuration
        # ----------------------------------------------------------------------

        run_config = RunConfig(
            timeout=JOB_TIMEOUT,
            max_retries=2,
            max_workers=1,
        )

        # ----------------------------------------------------------------------
        # Metrics
        # ----------------------------------------------------------------------

        metrics = [
            Faithfulness(
                llm=ragas_llm
            ),
            ContextPrecision(
                llm=ragas_llm
            ),
            ContextRecall(
                llm=ragas_llm
            ),
        ]

        # ----------------------------------------------------------------------
        # Run RAGAS
        # ----------------------------------------------------------------------

        print("=" * 80)
        print("STARTING RAGAS EVALUATION")
        print("=" * 80)

        print()

        eval_started = time.time()

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=ragas_llm,
            run_config=run_config,
            raise_exceptions=False,
            show_progress=True,
        )

        eval_minutes = (
            time.time()
            - eval_started
        ) / 60

        # ----------------------------------------------------------------------
        # Print result
        # ----------------------------------------------------------------------

        print()
        print("=" * 80)
        print("RAGAS RESULT")
        print("=" * 80)

        print(result)

        print(
            f"Evaluation time: "
            f"{eval_minutes:.1f} min"
        )

        # ----------------------------------------------------------------------
        # Convert to DataFrame
        # ----------------------------------------------------------------------

        df = result.to_pandas()

        # ----------------------------------------------------------------------
        # Attach metadata
        # ----------------------------------------------------------------------

        for key in (
            "id",
            "category",
            "source_section",
            "needs_multiple_chunks",
            "rag_seconds",
        ):

            df[key] = [
                extra[key]
                for extra in extras
            ]

        # ----------------------------------------------------------------------
        # Score columns
        # ----------------------------------------------------------------------

        score_cols = [
            column
            for column in (
                "faithfulness",
                "context_precision",
                "context_recall",
            )
            if column in df.columns
        ]

        # ----------------------------------------------------------------------
        # Per-question scores
        # ----------------------------------------------------------------------

        print()
        print("Per-question scores:")

        print(
            df[
                ["id", "category"]
                + score_cols
            ].to_string(
                index=False
            )
        )

        # ----------------------------------------------------------------------
        # Average per category
        # ----------------------------------------------------------------------

        if score_cols and df["category"].nunique() > 1:

            print()
            print("Average per category:")

            print(
                df.groupby("category")[score_cols]
                .mean()
                .round(3)
                .to_string()
            )

        # ----------------------------------------------------------------------
        # NaN check
        # ----------------------------------------------------------------------

        nan_counts = (
            df[score_cols]
            .isna()
            .sum()
        )

        print()
        print(
            "NaN per metric "
            "(failed/timed-out jobs):"
        )

        print(
            nan_counts.to_string()
        )

        if nan_counts.sum() > 0:

            print(
                "WARNING: some RAGAS jobs failed. "
                "Do not trust the corresponding "
                "metric average until NaN = 0."
            )

        # ----------------------------------------------------------------------
        # Save results
        # ----------------------------------------------------------------------

        RESULTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        stamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        tag = (
            args.tag
            or "golden"
        )

        csv_out = (
            RESULTS_DIR
            / f"ragas_{tag}_{stamp}.csv"
        )

        json_out = (
            RESULTS_DIR
            / f"ragas_{tag}_{stamp}_rows.json"
        )

        failed_out = (
            RESULTS_DIR
            / f"ragas_{tag}_{stamp}_failed.json"
        )

        # ----------------------------------------------------------------------
        # Save scores
        # ----------------------------------------------------------------------

        df.to_csv(
            csv_out,
            index=False,
            encoding="utf-8-sig",
        )

        # ----------------------------------------------------------------------
        # Save RAGAS input rows
        # ----------------------------------------------------------------------

        with open(
            json_out,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                rows,
                f,
                ensure_ascii=False,
                indent=2,
            )

        # ----------------------------------------------------------------------
        # Save failed RAG questions
        # ----------------------------------------------------------------------

        with open(
            failed_out,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                failed_questions,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print()
        print(
            f"Saved scores : "
            f"{csv_out}"
        )

        print(
            f"Saved rows   : "
            f"{json_out}"
        )

        print(
            f"Saved failed : "
            f"{failed_out}"
        )

    finally:

        await vectordb_client.disconnect()

        await db_engine.dispose()


# ==========================================================================
# CLI
# ==========================================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "RAGAS evaluation for mini-rag "
            "using the 42-question golden dataset."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Evaluate only the first N "
            "questions. 0 = all."
        ),
    )

    parser.add_argument(
        "--file-id",
        default=DEFAULT_FILE_ID,
        help=(
            "file_id of the indexed PDF "
            "to query."
        ),
    )

    parser.add_argument(
        "--json",
        default="",
        help=(
            "Path to the RAG golden dataset JSON. "
            "Defaults to "
            "evaluation/datasets/rag_golden_questions_42.json"
        ),
    )

    parser.add_argument(
        "--tag",
        default="",
        help=(
            "Label for this evaluation run."
        ),
    )

    parser.add_argument(
        "--ids",
        default="",
        help=(
            "Comma-separated question ids to "
            "evaluate, e.g. Q04,Q13,Q19."
        ),
    )

    parser.add_argument(
        "--category",
        default="",
        help=(
            "Evaluate only one category, "
            "e.g. Factual or \"Multi-hop\"."
        ),
    )

    return parser.parse_args()


# ==========================================================================
# Entry point
# ==========================================================================

if __name__ == "__main__":

    asyncio.run(
        main(
            parse_args()
        )
    )