# Professor Layton — historical candidate and evidence-grounded V2

This directory contains a **manually curated Persona candidate**, not an
LLM-extracted, canonically authenticated, or scientifically validated profile.
The display name is Professor Layton; the stable ID is `professor_layton`.

## V2 evidence and live candidate

V1's 35 scene summaries offered a useful starting point but limited middle-story
coverage and no fresh source inspection during its integration. V2 adds a
separate research condition: **71 original analytical paraphrases** across 18
US-indexed original-trilogy transcript pages (23 Curious Village, 24 Diabolical
Box, 24 Unwound Future). All 13 historical transcript pages were re-examined;
five additional pages broaden ordinary interactions and counterexamples.
The original corpus, Persona and all historical metadata/checksum files remain
byte-for-byte preserved. The thirteen excluded game quotations remain absent.

New assets:

- `corpus/persona_corpus_v2.jsonl`: seven-field analytical evidence corpus,
  **not spoken dialogue**. The existing loader accepts it and the selector
  returns 50 examples; no extraction prompt was run.
- `layton_persona_curated_v2.json`: manually curated eight-field live candidate.
- `metadata/source_inventory_v2.json`: inspected sources, dates, selected scene
  anchors, localization basis, source/reuse limits and controlled trait vocabulary.
- `metadata/entry_provenance_v2.json`: one entry per evidence ID, with exact URL,
  game/chapter, scene anchor, attribution basis, evidence kind and verification.
- `metadata/persona_v2_evidence_map.json`: every description/style/trait/rule and
  illustrative example maps to evidence IDs; example wording is newly authored,
  **not canonical**, and interpretations are explicitly qualified.
- `metadata/evidence_coverage_v2.md`: selection, counts, duplicate screening,
  exclusions, counterexamples, source restrictions, methodology and remaining gaps.
- `metadata/integration_manifest_v2.json` and `metadata/v2_SHA256SUMS`: V2
  integrity records plus a separate snapshot of historical file hashes. These
  supplement, never replace, the original research checksum manifest.

| Aspect | Original Persona | V2 refinement and evidence |
| --- | --- | --- |
| Courtesy and mentoring | Broadly courteous collaborative teacher | Retained, with room for his own confident judgment; map exercise `0003`, encouragement `0022`, Luke's expertise `0011`. |
| Disagreement | Polite but firm as a general rule | Concrete direct corrections and interruption of an arrest: `0020`, `0039`, `0054`. |
| Reasoning | Observation and conditional hypotheses | Retained; adds checking whether a solved puzzle actually changes the situation and accepting a physical alternative: `0057`. |
| Fallibility | Admits uncertainty | Adds mistaken identification and apology, not only unknown information: `0005`, `0026`, `0052`. |
| Social tone | Warmth and understated humor | Replaces an unmeasured British-English style label with courteous English, small asides and playful exchanges: `0021`, `0029`, `0049`. No accent or lexical-frequency claim. |
| Emotional range | Composure with possible grief | Retains compassion; allows limited exasperation, personal attachment, urgent directness and broken farewell speech: `0062`, `0058`, `0067`, `0070`. These are contextual, not mandatory emotions. |
| Puzzles | Teaching, with anti-catchphrase restrictions | Includes both engagement and deferral; no rule that every problem is a puzzle: `0007`, `0047`, `0057`. |

IDs in the table abbreviate the `layton_v2_` prefix. The map ties each exact
Persona element to its supporting rows. V2 is slightly shorter in rule count
(9 versus 10); expansion of evidence was not used to inflate the profile.
Its six new example messages are hypothetical illustrations whose behavior/style
is evidence-informed, not fabricated events passed off as observations.

The [coverage report](metadata/evidence_coverage_v2.md) documents the gate for
promoting V2 as a live **candidate**, not scientific approval. The unofficial
transcripts were inspected through their US index; marked HD/mobile additions
were excluded. Their original-DS wording and audio were not independently
verified. No reuse license was found in the inspected transcript pages, and
publisher pages do not grant permission to redistribute game text. Only short
original analytical notes and source references are newly committed.

Structural consistency means the same eight-field Persona schema. Evidence
coverage means inspectable scenes support relevant behavior. **Methodological
equivalence has not been established** with Sherlock/Poirot's literary-dialogue
corpora. No LLM extraction, live Copilot comparison, or scientific fidelity/
recognizability validation was performed. More independent primary-game checks,
ordinary social contexts, and dialogue-level style evidence remain needed.

## Historical V1 imported evidence and provenance

The supplied archive contained 48 records. `corpus/persona_corpus.jsonl` retains
only the 35 original English editorial summaries (`layton_0001`–`layton_0035`),
byte-for-byte by line, with the seven existing corpus keys. They describe
attributed behavior and dialogue; they are **not speech samples or quotations**.
Their underlying sources remain unofficial US-English fan transcripts.

All 13 quote texts (`layton_0036`–`layton_0048`) are omitted from the versioned
corpus and from any archived corpus copy in this repository. Independent game
verification and redistribution legitimacy were not established. This decision
asserts neither legal clearance nor infringement. No full scripts, game assets,
or new game quotations were imported.

- `metadata/source_inventory.json`: unchanged inventory of 17 sources, including
  13 unofficial transcript documents and four publisher identity/theme pages.
  The later-continuity publisher profile is not original-trilogy style evidence.
- `metadata/entry_provenance.json`: unchanged mapping of all 48 original IDs;
  excluded IDs retain source references and verification status, without text.
- `metadata/example_message_provenance.json`: all six Persona examples are
  original illustrative messages, not canonical dialogue.
- `metadata/methodology_and_qa.md`: unchanged research-package methodological
  discussion; its 48-row counts describe the supplied package, not this corpus.
- `metadata/research_SHA256SUMS`: original nine-file research manifest. All nine
  checks passed on the extracted package before filtering. It is historical,
  not a checksum command to run against this directory: excluded/renamed files
  deliberately do not exist at its original paths.
- `metadata/integration_manifest.json`: archive hash, audited commit, inclusion
  and exclusion IDs, decisions, and current corpus/Persona hashes.

The original ZIP and full extracted research package remain outside the repo.
Checksums establish artifact integrity, not authenticity or source reliability.
No independent web/game verification was performed during V1 integration; V2
source inspection is described above and is not primary-game verification.

## Critical review and methodological limits

The summaries support a plausible initial profile of courteous collaborative
questioning, observation, conditional reasoning, mentoring, humility and care.
Contrasting scenes include uncertainty, distress and forceful action, reducing
the risk of a uniformly serene caricature. The supplied Persona is retained
unchanged as a reviewable candidate: no additional traits or quotations were
invented during integration.

However, confidence values are editorial attribution judgments conditional on
unverified transcripts, not calibrated probabilities. Some summaries overlap
conceptually (for example the future-letter hypothesis); there are no exact
normalized-text duplicates. Coverage favors Luke, teaching, dramatic endings
and game mechanics; spoilers occur in evidence contexts. British-English style,
humor and anti-catchphrase rules are interpretive choices, not demonstrated
lexical measurements. Six authored examples can influence generation without
proving fidelity. The corpus's English language was reviewed manually; structural
tests do not authenticate language, quotations, or character quality.

Sherlock/Poirot were seeded primarily from literary dialogue. The supplied Layton
research used mixed editorial summaries and unofficial excerpts; the imported
subset is now summary-only. Existing extraction conventions and
`prompts/extract_persona.md` expect representative speech samples. Its actual
current wording says “text examples” and “representative, corpus-supported
lines”; it does not safely establish that editorial summaries are spoken lines.
**Do not use this corpus with the unchanged extraction workflow as if it were
dialogue.** No extraction run was used to produce this candidate, and extraction
defaults/prompts were not changed. This approach is not methodologically
equivalent to the existing characters. Fair confirmatory comparisons require a
separate study-design decision, consistent evidence/extraction conditions, and
appropriate source verification before recognition claims.

## Current runtime and historical controls

`configs/characters.yaml` registers `layton` third. Its `live_persona_path`
selects `layton_persona_curated_v2.json` for Copilot conversations. The historical
`persona_fixture_path` still selects `layton_persona_curated_candidate.json`
for mock conversations; `corpus_path` still selects the original 35-row corpus.
The V2 evidence corpus is deliberately explicit research input, not silently
substituted into the speech-oriented extraction workflow. The deterministic
mock reply remains `tests/fixtures/layton_agent_response.txt`.

Both `baseline_v1` and `dialogue_v2` render the complete selected Persona through
the unchanged runtime. The stable identity is still `professor_layton` /
Professor Layton, validated by the existing model and catalog identity checks.
There is no Layton-specific loader branch or additional LLM call.

Sherlock/Poirot retain their generated live profiles and synthetic mock controls;
Kogoro retains his existing curated candidate. No other character configuration,
prompt template, provider, selector, or investigation behavior changed.

No runtime or schema code changes were necessary. Conversations UI automatically
renders and initially selects the third catalogue entry after restart; no UI
files were edited. The investigation lobby also lists catalogue entries but
marks Layton unsupported. Existing investigation capabilities and runtime reject
Layton; no investigation fixtures or agent support were added. The blind-rater
interface and two-character pilot are unchanged.

See [Sprint 8.3 completion](../../docs/sprint_8_3_completion.md) for historical
V1 verification and the [V2 coverage report](metadata/evidence_coverage_v2.md)
for the current source audit.
