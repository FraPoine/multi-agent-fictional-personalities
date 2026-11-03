# Layton V2 — evidence coverage and QA

Audit baseline: `9b13cddc6349d823caf8430e9b2f5a46caf36489`.
Source inspection: 2026-11-03. This report concerns V2, not the historical
48-entry research package or its filtered 35-entry repository corpus.
Evidence and anchors contain original-trilogy spoilers.

## Selection and scope

The original corpus has 35 editorial summaries. V2 contains **71 newly written
analytical observations** from **18 inspected US-indexed transcript pages**:
all 13 historical transcript sources were revisited, with five additional pages
(CV Chapters Three/Six, DB Chapter Two and Puzzle Quits & Returns, UF Chapter Four).
V2 replaces overlapping summary formulations within a separate artifact; it does
not append the old rows to inflate the count. Original files remain unchanged.
Each row has the historical seven keys and a distinct named scene/behavior anchor.

Only LAYTON-labelled speech is used for his responses; Luke, Future Luke,
Claire, and others provide conversational circumstances, not replacement Layton
utterances. Optional branches are observations of possible game responses,
not claims that all alternatives happened in one canonical playthrough.

Selection favored explicit corrections, mistaken assumptions, everyday social
exchanges, practical choices and changes under pressure. Curated scene sampling
is not a representative sample of all dialogue. It does not estimate behavioral
frequencies. Record counts and checksums do not establish research quality.

## Coverage

| Game | Records |
| --- | ---: |
| Professor Layton and the Curious Village | 23 |
| Professor Layton and the Diabolical Box | 24 |
| Professor Layton and the Unwound Future | 24 |

| Source | Records |
| --- | ---: |
| `CV_PRO` | 4 |
| `CV_CH3` | 4 |
| `CV_CH5` | 5 |
| `CV_CH6` | 4 |
| `CV_CH8` | 4 |
| `CV_PUZZLE` | 2 |
| `DB_PRO` | 4 |
| `DB_CH1` | 5 |
| `DB_CH2` | 4 |
| `DB_CH6` | 4 |
| `DB_CH7` | 5 |
| `DB_PUZZLE` | 2 |
| `UF_PRO` | 4 |
| `UF_CH1` | 4 |
| `UF_CH4` | 4 |
| `UF_CH12` | 4 |
| `UF_CH13` | 4 |
| `UF_EPI` | 4 |

Behavioral dimensions overlap; totals below are annotations, not independent trials.

| Dimension | Records |
| --- | ---: |
| counterexamples | 21 |
| pressure | 9 |
| reasoning_style | 30 |
| social_behavior | 39 |
| speaking_style | 22 |
| temperament_and_emotion | 23 |

| Corpus trait | Records |
| --- | ---: |
| curiosity | 4 |
| decisiveness | 10 |
| emotional_expression | 4 |
| emotional_restraint | 4 |
| empathy | 16 |
| humility | 6 |
| humor | 4 |
| interaction_with_luke | 17 |
| moral_courage | 3 |
| observation | 10 |
| pedagogy | 6 |
| politeness | 13 |
| reasoning_style | 23 |
| social_behavior | 7 |
| speaking_style | 17 |
| uncertainty | 14 |

## Duplicate and attribution checks

- Unique stable IDs: 71; seven keys per row.
- Exact normalized-text duplicates: 0 (case-fold and collapse whitespace).
- Candidate near-duplicates at character-sequence similarity >= 0.80: 0.
  This is a screening heuristic, not a semantic-duplicate proof.
- Manual overlap review keeps one record per observation. Distinct behavior in
  a shared scene may remain: the accusation/biographical test (`0020`) and the
  wrong-answer personal aside (`0021`), for example, serve different dimensions.
  IDs in this report abbreviate the `layton_v2_` prefix.
- Cross-scene corroboration is intentionally retained (animal expertise, for
  example). Neither parallel scenes nor related tags are counted as independent
  empirical confirmation. Main and quit-branch versions of the same waiter
  exchange were not duplicated.
- Four optional quit-response records: two each from CV and DB. Puzzle-related
  chapter scenes remain, but repeated UI failure lines were not harvested.
- Original thirteen excluded quote texts (`layton_0036`–`layton_0048`) remain
  excluded. No canonical game dialogue is newly redistributed.

## Counterexamples and exclusions

| Simplification tested | What the inspected context supports |
| --- | --- |
| Always composed | Captivity includes transcribed effort/strain (`0043`); Claire's farewell breaks measured speech (`0070`). These do not establish habitual anger. |
| Always agrees politely | Accusation challenge (`0020`), interruption of an arrest (`0039`), and direct rejection of Luke's exit theory (`0054`). |
| Always teaches, never decides | Urgent entry to the mentor's flat (`0027`) and rescue demands (`0064`, `0067`). |
| Never mistaken | Misidentification of the photograph and apology (`0005`); a puzzle solution fails to open the door (`0057`). |
| Always knows the answer | Unknown flat (`0026`), age discrepancy (`0042`), future letter (`0048`) and changed surroundings (`0052`). |
| Every problem requires a puzzle | Initial reluctance to be diverted (`0007`), leaving a puzzle for a missing-child search (`0047`), and accepting a physical solution (`0057`). This does not deny frequent in-game puzzle references. |

Rejected or limited material:

- The CV prologue's explicitly marked HD-mobile opening and added charm
  tutorial; other marked mobile interface additions. No remake-only event is
  included. Original DS wording was not independently authenticated.
- The DB prologue mentor's letter is attributed to Schrader. It supports
  circumstances of Layton's concern, not Schrader's speaking style as Layton's.
- UF Chapter Four's cuff-link rescue is mostly Luke/Future Luke dialogue; it
  was not repackaged as Layton's own plan. His separate bee referral is included.
- The epilogue's extended rescue speech belongs to Celeste, not Layton. Only
  Layton's stated plan to return after securing his passengers is used (`0068`).
- Anton-as-vampire banter was not used to assert a settled belief or a universal
  comic trait. Its interpretation is less secure than the selected exchanges.
- The older summary combining DB pitcher workmanship and tea was not carried
  forward as evidence of a measured lexical style. No UK vocabulary frequency,
  spoken accent, or quantified syntax claim is supported by these paraphrases.
- No claim of habitual frustration, universal selflessness, unfailing humility,
  or perfect knowledge is justified. The Marzano withdrawal (`0062`) supports a
  limited reading of exasperation, not a requirement to sound irritated.

## Accessibility, authenticity and reuse

The inspected pages were accessible as rendered text. The inventory records
exact URLs, inspection date, role, localization basis and selected anchors.
The site's [US navigation](https://professorlaytontranscripts.wordpress.com/)
separates US/UK material. Its [About page](https://professorlaytontranscripts.wordpress.com/about/)
explains speaker labels, scene separators and interaction markers. These support
traceability, not game authenticity. Some pages intermingle marked mobile-only
additions. No independent game copy, footage, audio or localization check was
performed; all gameplay evidence remains unofficial and primary-game-unverified.
No complete source snapshots are committed; live pages may change.

No reuse license was found in the inspected index, About, or post content.
Public access does not grant redistribution rights. The inspected
[LEVEL-5 mobile page](https://www.laytonseries.com/curiousvillage/uk/)
expressly restricts asset republishing; its content is not imported.
The [Nintendo guide](https://www.nintendo.com/en-gb/News/2011/The-Beginners-Guide-to-the-Professor-Layton-Games-253601.html)
and [original-game page](https://www.nintendo.com/en-gb/Games/Nintendo-DS/Professor-Layton-and-the-Curious-Village-272563.html)
corroborate broad identity/game role only. They are UK publisher copy, not US
dialogue evidence. No official image, script, full passage or gameplay quotation
is newly committed. Original analytical notes are used instead; no claim of
rights clearance or authenticated canonical dialogue is made.

## Curation method and quality gate

The loader accepts all 71 rows and the unchanged selector returns 50. This is
structural/selection compatibility only. The generic extraction template asks
for representative corpus-supported lines; paraphrases cannot supply authentic
speech samples or measured syntax. No LLM extraction, provider call or new
production extraction framework was used. V2 remains manual evidence-grounded
curation with original illustrative messages, all individually marked in the
Persona evidence map. Example situations are invented illustrations, not game
observations or evidence discovered in a runtime case.

[RoleLLM](https://aclanthology.org/2024.findings-acl.878/) motivates separating
profile, contextual evidence and speaking style. [CoSER](https://arxiv.org/abs/2502.09082)
motivates retaining circumstances and experiences alongside dialogue evidence.
These are methodological references, not replicated extraction/training methods,
datasets, evaluation protocols or validated results.

The technical/data gate permits promotion as a **live conversation candidate**:
source-scene inspection completed; observation wording and attribution reviewed;
no exact duplicate; every significant Persona element mapped; illustrative and
interpretive choices labelled; original artifacts preserved. This is not an
independent human review, legal clearance, primary-source authentication or a
scientific fidelity gate. The live catalog path selects V2; mock Persona, mock
response, and catalog corpus path remain the historical control. Selecting V2
is a new Persona condition, independent of the two unchanged prompt variants.

## Remaining gaps

Independent US-DS verification, dialogue-level lexical/intonation evidence,
rights assessment for any future quotation corpus, and independent annotation
remain outstanding. More ordinary middle-story interactions would improve
balance. Luke still appears frequently; his companion role and puzzle mechanics
are intrinsic sampling confounds. Emotional-loss examples are rare and
context-specific. There is no calibrated confidence, inter-annotator agreement,
frequency estimate, live behavioral comparison, or recognizability validation.

All characters retain structural consistency through the same eight-field
Persona schema. V2 improves documented evidence coverage; it does **not**
establish methodological equivalence to Sherlock/Poirot's literary-dialogue
corpora, or prove improved character fidelity because it is larger.
