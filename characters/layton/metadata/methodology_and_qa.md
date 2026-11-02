# Sprint 8.3 — Professor Layton: methodology and critical review

Repository checked: `FraPoine/multi-agent-fictional-personalities`, `main` at `12b34cc6691cbfe1598037553dd7dc373ee6008a` (2026-11-02).

## Corpus status
- 35 original English-language **editorial evidence summaries**, plus 13 short, distinctly labelled excerpts from 13 distinct US-English fan-transcript scenes/documents across the original three titles; 4 publisher pages independently corroborate general character identity and theme.
- NOT an authenticated or licensed complete game-dialogue corpus. Source pages are unofficial transcripts of protected game text and have **not** been independently checked against game footage or a legal game copy.
- The seven keys `id`, `character_id`, `source`, `text`, `context`, `traits`, and `confidence` match the Sherlock/Poirot JSONL structural contract. `source` is a short source ID mapped to full title, edition and URL in `source_inventory.json`.
- `text` is EITHER an original summary OR a brief quote attributed to Layton by the **unofficial** transcription. `context` and `entry_provenance.json` label the type per entry. Short quotes are exact excerpts from the linked transcription, **not independently checked canon**. Never relabel summaries as dialogue, nor transcripts as directly verified primary-source text.
- Confidence estimates speaker/event attribution *conditional on the cited transcription*. They are editorial judgments, **not** verified probabilities, primary-source verification scores, or evidence of persona quality.
- No dialogue from unrelated characters is presented as Layton’s own. Short quotations are limited to **one per source page**, each under 25 words. No full scripts, copyrighted cutscenes or game assets are distributed.

## Existing process and methodological gap
- Original Sherlock and Poirot corpora use lengthy quoted dialogue from nine literary works each, with source-by-source extraction, >=0.85 confidence, and seed-controlled source/trait coverage selection.
- Repo `prompt.py` constants: confidence threshold 0.85, at least two examples per source when available, three per trait when available, target 50 examples and random seed 42.
- Existing `prompts/extract_persona.md` assumes corpus examples are **actual text examples of a character’s speech**; these Layton rows instead describe speech/behavior. Running that template unchanged may infer traits, but cannot learn actual lexical or syntactic patterns in the same way.
- **Therefore the draft is explicitly manually synthesized from cited scene evidence, NOT an output of the same LLM-based extraction pipeline. This is a material experimental confound.** Before a confirmatory recognizability experiment, either (1) obtain short legally acceptable, independently checked dialogue excerpts and run identical extraction on all three characters, or (2) consistently apply the evidence-summary methodology across all agents and record the change as a new experimental condition.
- Be conservative about claims of measured fidelity; there has been no rater evaluation, blind test, linguistic validation, transcript authentication, or human expert annotation.

## Selection criteria
1. Prefer older original trilogy, US English, speaker clearly labeled as `LAYTON` by the transcription.
2. Select varied behavior: investigation, evidence, teaching, disagreement, anxiety, social care, ordinary interests, high-stakes decisions and rare strong emotion.
3. Avoid duplicates, purely plot-summary assertions and overconcentration in puzzle failure/return UI or famous slogans.
4. Cross-check broad identity against Nintendo / LEVEL-5, and label interpretation separately.
5. Avoid UK/US localization mixing, remake-exclusive lines and dialogue from unreleased/newer games.

## Coverage summary
Sources: {'CV_CH5': 3, 'CV_CH8': 5, 'CV_PRO': 5, 'CV_PUZZLE': 3, 'DB_CH1': 5, 'DB_CH6': 3, 'DB_CH7': 5, 'DB_PRO': 3, 'UF_CH1': 3, 'UF_CH12': 3, 'UF_CH13': 3, 'UF_EPI': 4, 'UF_PRO': 3}
Traits: {'curiosity': 3, 'emotional_expression': 3, 'emotional_restraint': 12, 'empathy': 10, 'humility': 9, 'interaction_with_luke': 16, 'moral_courage': 4, 'observation': 7, 'pedagogy': 10, 'politeness': 11, 'reasoning_style': 18, 'social_behavior': 16, 'speaking_style': 22, 'uncertainty': 17}

### Evidence-backed conclusions
- **Gentlemanly restraint is operational, not decorative:** he maintains manners under provocation and proposes clearing litter (`CV_PRO`, `DB_CH1`, `CV_CH8`).
- **He is a teacher, not a competitive show-off:** he lets Luke attempt the problem, offers encouraging feedback, teaches planning (`CV_PRO`, `CV_PUZZLE`, `DB_CH1`).
- **Reasoning includes cautious language and admitting ignorance:** observations, alternate explanations, conditional hypotheses (`CV_CH8`, `DB_CH7`, `UF_PRO`, `UF_CH1`).
- **Warmth and moral courage are not the same as constant serenity:** he protects others and sometimes suffers openly (`UF_CH13`, `UF_EPI`).
- **He dislikes the label ‘detective’ for himself in an introductory exchange:** not a blanket ban on investigating or being recognized for solving cases (`CV_PRO` vs publisher descriptions).

### Interpretive design choices (not direct factual claims)
- `example_messages` are **six newly written illustrations**, not game lines; all have sidecar item-level provenance in `example_message_provenance.json`.
- A few natural British-English turns of phrase and inviting questions are extrapolated from the transcript’s tone. There was **no quantitative lexical study**.
- Limiting puzzle catchphrases, top-hat references and tea mentions is an anti-caricature generation policy, not a recurring canonical command to Layton.
- The moral-courage instruction is inferred from concrete rescue scenes, not evidence that he would act identically in every imagined threat.

## Character differentiation and risks
| | Sherlock Holmes | Hercule Poirot | Professor Layton |
|---|---|---|---|
| Investigation | Fine observation, deduction, incisive challenge | Psychological insight, internal method, orderly synthesis | Observation and conditional reasoning, often taught collaboratively |
| Interpersonal stance | Reserved and sometimes sharp | Polite but proudly self-confident, theatrical | Civil mentor, gentle encouragement, readiness to help |
| Typical self-presentation | Consulting detective | Private detective who values his little grey cells | Archaeology professor and puzzle enthusiast, not self-styled police detective |
| Important counterexample | Holmes has compassion too | Poirot can revise his theories | Layton can be forceful, be unsure and openly grieve |

Potential bias: trilogy game dialogue includes action/menu prompts, not only ordinary social conversation; far less natural conversational variation than the books. Story selection favors Luke and the most dramatic endings. The English localization differs across regions. A rater may recognize Layton through puzzle references instead of a distinct communicative style. Long-form literary passages vs game-based short interaction patterns differ in genre, length, editorial treatment and source licensing.

## Next QA gates for Codex and the study
- Authenticate each high-impact passage against the actual US game version or an independently inspectable recording with title, chapter, dialogue and timestamp.
- If adopting original-quote corpus, secure rights / legal review for the intended distribution and keep passages short and directly attributable.
- Specify whether extraction input is dialogue or evidence summary. Never silently switch semantics across agents.
- Log source version, extractor prompt hash, model/provider version, seed, example selection and any human edits.
- Blind-compare on **novel neutral topics** without names, puzzle catchphrases or Luke; score per-character confusion and error bars; pre-screen rater familiarity.
- Do not report the current draft as scientifically validated.
