# Three-persona benchmark: source import

This is a development data pipeline, not a human study or a claim of character fidelity. It makes no model calls. The review, rating, and analysis workflow is described in [the benchmark protocol](benchmark_three_personas_v1.md).

Generate six conversations separately with the existing conversation service, using the exact topics and speaker orders in `configs/benchmark_three_personas_v1.yaml`, six turns, provider `copilot`, `dialogue_v2`, and the frozen explicit model `gpt-5.6-luna` for every run. Completed local Copilot artifacts record this identifier; current availability is not guaranteed. The importer rejects runs unless the configured, run and message model identities match the versioned configuration; an SDK default or missing model evidence cannot pass. New live runs record the hashes of the exact persona bytes loaded, their source paths, the selected model, and the prompt template hash. These fields provide operational provenance, not cryptographic proof against tampering. Historical runs missing these fields cannot be strictly verified and are rejected; hashing current persona files later cannot establish what generated an old run.

Place the six saved run directories under `outputs/conversations/runs/`. Create a YAML manifest such as:

```yaml
sources:
  scenario_01: run_id_01
  scenario_02: run_id_02
  scenario_03: run_id_03
  scenario_04: run_id_04
  scenario_05: run_id_05
  scenario_06: run_id_06
```

Run from the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/prepare_three_persona_benchmark.py sources.yaml --output-root outputs
```

The importer checks the saved run and message artifacts agree, verifies all configuration and provenance fields, and rejects mismatches before publication. It uses the second contribution of each speaker; if that contribution is unusable, it tries the first. It rejects errors, duplicate selected texts, source metadata, self-identification, and any occurrence of the speaker's own name. An initial direct address to another character is replaced with `[name]`; other name references are rejected because masking them may change substantive meaning. No other stylistic editing is performed. Duplicate detection is case-insensitive after masking. If no eligible fallback exists, preparation fails. Public IDs are stable hashes of private source identifiers; do not disclose those identifiers to raters.

The directory `outputs/evaluation/benchmarks/three_personas_v1/` contains:

- `trials_public.jsonl`: opaque ID, response, and three candidate IDs only.
- `answer_key.jsonl`: private answer, original response, scenario, source message and turn, and mask count.
- `benchmark_manifest.json`: private configuration and source artifact checksums.
- `leakage_review.json`: private selected and excluded candidate decisions and mask counts.

Only the public file is suitable for a rater-facing application. **Manual leakage review is required before any public use.** Automated rules cannot detect every alias, implicit identification, contextual clue, or meaning changed by a mask. Inspect the review report and compare selected original texts with displayed texts; if masking obscures substantive meaning or an identity remains inferable from an explicit reference, reject the set and document the issue. These rules do not remove characteristic writing style.

Before recording approval, the review command checks the public schema and balance, private answers and source references, frozen configuration and provenance, and leakage-review selections and mask counts. This does not replace manual inspection of all public and original texts. Trial submissions are checked against the next unanswered position under the persistence lock.
