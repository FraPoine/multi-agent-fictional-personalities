# Professor Layton conversation candidate — Sprint 8.3

This directory contains a **manually curated Persona candidate**, not an
LLM-extracted, canonically authenticated, or scientifically validated profile.
The display name is Professor Layton; the stable ID is `professor_layton`.

## Imported evidence and provenance

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
No independent web/game verification was performed during implementation.

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

## Runtime and fixtures

`configs/characters.yaml` registers `layton` third. The historical field
`persona_fixture_path` points directly to
`characters/layton/layton_persona_curated_candidate.json`. Both the mock loader
and real Copilot conversation loader read that exact eight-field `Persona`.
There is no generated-Persona lookup, silent extraction, or duplicate synthetic
Persona file. A separate `tests/fixtures/layton_agent_response.txt` is original
synthetic text used only as the deterministic mock reply. Mock orchestration's
existing “synthetic persona fixture” error wording reflects the older fixtures;
it does not describe the provenance of this candidate.

Sherlock/Poirot data and their existing fixture-based loading remain unchanged.
Their real conversation route still loads their catalogued synthetic Persona
fixtures; it does not load their `outputs/` extraction artifacts. This preexisting
limitation is outside the Layton-specific change.

No runtime or schema code changes were necessary. Conversations UI automatically
renders and initially selects the third catalogue entry after restart; no UI
files were edited. The investigation lobby also lists catalogue entries but
marks Layton unsupported. Existing investigation capabilities and runtime reject
Layton; no investigation fixtures or agent support were added. The blind-rater
interface and two-character pilot are unchanged.

See [Sprint 8.3 completion](../../docs/sprint_8_3_completion.md) for verification.
