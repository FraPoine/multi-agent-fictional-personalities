# Three-persona blind identification development protocol

Finalize and version this protocol before collecting genuine responses. Record later methodological changes as deviations or exploratory analyses. This is a development benchmark, not the final four-character experiment.

The research question is whether blind evaluators identify fictional-persona-conditioned agents above the three-way chance level. The null hypothesis is accuracy of 1/3; the directional alternative is greater than 1/3. Recognition is measured directly; confidence is subjective certainty, and neither establishes behavioral fidelity or authentic personality reproduction.

Sherlock Holmes and Hercule Poirot use the generated live personas and Professor Layton uses the manually curated evidence-grounded V2 persona. Their exact paths and SHA-256 hashes are frozen in `configs/benchmark_three_personas_v1.yaml`. All six scenarios use the same explicit Copilot model and `dialogue_v2` prompt hash, six turns, and rotating round-robin order. One conversation per scenario yields 18 trials, one per character per scenario, selected from second contributions with the deterministic first-contribution fallback. See [source import and leakage policy](three_persona_benchmark_data_pipeline.md) for exact validation and masking rules. The simulation seed does not make live model outputs deterministic.

Before exposure, inspect all 18 public responses alongside the private leakage review and original texts, then explicitly approve with the command below. If a trial is unsafe, reject the set; correct the source or deterministic preparation rule, document the deviation, rebuild the whole set and repeat review. Do not hand-pick a more recognizable response. Approval binds the reviewed public trials, answer key, manifest and leakage report by SHA-256. Changed artifacts invalidate it. The answer key and other private files must not be shared with raters.

Recruit three voluntary adult raters familiar with the candidates when feasible; record recruitment and deviations locally. Raters choose a pseudonymous ID and rate familiarity independently for each character: 0 unknown, 1 name only, 2 reasonably well, 3 very well. Familiarity is immutable once submitted and precedes exposure to response text. All participants may complete the task; the primary descriptive sample consists only of raters who complete all 18 trials and score at least 2 for all three characters. A manually chosen ID is not strong authentication. Run the interface locally and do not expose it publicly without reviewing access control and privacy. Do not use names or email addresses as IDs.

Each rater sees an anonymous response, three candidate names, and a required confidence from 1 to 5. Trial and candidate orders use Python's seeded PRNG initialized from SHA-256 of the configured seed and pseudonymous rater ID. The same ID resumes the same order. These orders are independent of the answer key. The study stores familiarity, choices, confidence and timestamps separately; no additional personal information is required.

The primary metric is correct identifications divided by all identifications from eligible complete raters. If none qualify, it is unavailable. Secondary descriptions include all submitted judgments, per-character and per-rater accuracy, a true-by-selected confusion matrix, counts by scenario, familiarity, mean confidence by correctness, and pairwise agreement over overlapping ratings. Incomplete ratings are included in secondary results, never treated as incorrect. A 95% Wilson interval is a naive descriptive interval: it assumes independent judgments and does not account for shared raters or source conversations. No confirmatory significance claim follows from a small pilot or from accuracy above chance. Report negative and inconclusive results honestly.

The older technical mock pilot uses two characters, synthetic messages and a 1/2 chance baseline; it remains separate. A later four-character study has a 1/4 chance baseline and requires its own frozen protocol, data and validation. Layton's evidence is methodologically different from the literary-dialogue sources used for Sherlock and Poirot.

## Operator workflow

Prepare genuine source runs separately, then import without further model calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/prepare_three_persona_benchmark.py sources.yaml --output-root outputs
cat outputs/evaluation/benchmarks/three_personas_v1/trials_public.jsonl
cat outputs/evaluation/benchmarks/three_personas_v1/leakage_review.json
cat outputs/evaluation/benchmarks/three_personas_v1/answer_key.jsonl
PYTHONPATH=src .venv/bin/python scripts/review_three_persona_benchmark.py outputs/evaluation/benchmarks/three_personas_v1 --reviewer reviewer_001 --confirm-reviewed
PYTHONPATH=src .venv/bin/python scripts/run_three_persona_rater_web.py outputs/evaluation/benchmarks/three_personas_v1
PYTHONPATH=src .venv/bin/python scripts/analyze_three_persona_benchmark.py outputs/evaluation/benchmarks/three_personas_v1
cat outputs/evaluation/benchmarks/three_personas_v1/report.md
```

The reviewer must inspect the public trials and private report before acknowledging review. The analysis command works with no ratings and reports unavailable results rather than fabricating them. Save source runs, versioned config and protocol, review approval, response files and report securely. Generation-time metadata records the persona files loaded but is not cryptographic proof against tampering; older runs without this evidence cannot pass strict import.

## Related work

[RoleLLM / RoleBench](https://aclanthology.org/2024.findings-acl.878/) motivates character-level assessment across contexts. [InCharacter](https://aclanthology.org/2024.acl-long.102/) distinguishes personality assessment from surface recognition. [CoSER](https://proceedings.mlr.press/v267/wang25dk.html) motivates attention to character behavior in conversational context. [ConSiDERS](https://aclanthology.org/2024.acl-long.63/) motivates explicit human-evaluation procedures and attention to bias. This protocol does not reproduce the complete methods or architectures of those papers.
