import json, sys
from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
from evaluation.ragas_evaluator import build_ragas_llm

rows = json.load(open(sys.argv[1], encoding="utf-8"))
llm = build_ragas_llm()
res = evaluate(
    Dataset.from_list(rows),
    metrics=[Faithfulness(llm=llm), ContextPrecision(llm=llm), ContextRecall(llm=llm)],
    llm=llm,
    run_config=RunConfig(timeout=1800, max_retries=2, max_workers=1),
    raise_exceptions=False,
)
print(res)
print(res.to_pandas()[["faithfulness", "context_precision", "context_recall"]])