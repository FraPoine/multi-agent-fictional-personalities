# Sprint 8.4 — Kogoro Mori Research, Methodology and Quality Review

## Status and scope
- Candidate, **not scientifically validated**. Repository was inspected read-only at `c96cfdb8a1c326c79358c0c58e75b9c6ded74b45` on 2026-11-02.
- Display name: **Kogoro Mori**. Stable ID: `kogoro_mouri`. Japanese: 毛利小五郎 (Mōri Kogorō). TMS English: Kogoro Mori. VIZ legacy English: Richard Moore.
- Manga by Gosho Aoyama is the preferred canonical continuity; **original manga panel text has not been independently accessed or authenticated**. Shonen Sunday and Shogakukan official publisher synopses anchor many original-manga incidents and volume/file references; Yomiuri TV official anime synopses supply additional detail. No original manga dialogue or panels were independently read.
- All 36 corpus texts are **newly written English editorial evidence summaries**. No manga/anime dialogue has been reproduced; there are **zero direct quotes** in the corpus. Exactly seven required keys are retained for the current JSONL loader. See `entry_provenance.json` to recover the content type and attribution for every record.
- Confidence scores (0.89–0.99) are subjective editorial judgments about how strongly a published synopsis supports an event, **not** calibrated probabilities, original Japanese speaker attribution, or measured fidelity.

## Evidence and interpretation boundaries
### Supported by official summaries
- Kogoro is a former police officer, working private investigator, with an inflated reputation as Sleeping Kogoro largely due to Conan's concealed contributions (`SHOG_SELECTION`, `YTV_CHARACTER`, `TMS_CHARACTER`, `YTV_EP003`).
- Fame, public recognition and relationships can elicit boastful, excited or defensive behavior (`YTV_EP305_306`, `YTV_EP589_590`).
- He detects physical clues and reconstructs some cases; however, *assisted* scenes must not be called independent solutions (`SHOG_REUNION`, `SHOG_BLUECAT`, `YTV_EP589_590`).
- His reasoning may begin with imperfect practical hypotheses; contrary evidence can leave an explanation incomplete (`YTV_EP911`, `YTV_EP919`).
- Personal bonds create genuine stakes and a more forceful investigative commitment (`YTV_EP027_028`, `YTV_EP589_590`).

### Explicit interpretive generation choices
- Modern, direct, energetic **English voice**: plausible English rendering of expressive scenes, *not a validated lexicometric profile from Japanese or a single English dub*.
- Occasional defensiveness and hasty conjecture: scene-derived tendencies rather than always-on error or disagreement policies.
- Synthetic examples are illustrative, not lines from manga, anime or any dub; see `example_message_provenance.json`.
- There is no reliable direct evidence in this subset that Kogoro *frequently says* particular English phrases, routinely admits errors verbally, or always cooperates with other detectives. Do not claim it.

## Comparison against existing characters
| Attribute | Sherlock | Poirot | Layton | Kogoro candidate |
|---|---|---|---|---|
| Approach | explicit observation and deduction | orderly psychological inquiry | collaborative patient puzzles | practical first theory, sometimes rushed but revisable |
| Social stance | restrained, sometimes cutting | confident and theatrical | patient and courteous | sociable, proud, reactive to embarrassment |
| Emotion | usually contained | dramatic in measured bursts | restrained with caring undertones | quick irritation or enthusiasm; protective where personally invested |
| Disagreement | challenges weak inferences | tests facts vs theory | asks guiding questions | may initially defend a position, should revise if evidence undermines it |
| Attribution hazard | source dialogue vs model defaults | French expressions are strong cues | summaries vs dialogue | Conan regularly speaks with his voice; must avoid attribution leakage |

## Major threats to recognizability validity
1. **Unequal method**: Sherlock/Poirot: literary dialogue → LLM extraction. Layton: editorial summaries → manually curated candidate. Kogoro: editorial summaries → manually curated candidate. Comparisons conflate persona, media, extraction method and evidence modality.
2. **Localizations**: original Japanese name/speech differ from English anime and VIZ's Richard Moore. Wording created here cannot demonstrate actual canonical English idiolect.
3. **Credit misattribution**: 'Sleeping Kogoro' scenes often are Conan impersonating him, not examples of his thought process.
4. **Selection bias**: curated detective moments, family incidents and gags may overrepresent extremes; this is **not a representative random sample** of the manga.
5. **Style shortcut**: strong confidence, celebrity references and comedy may allow raters to guess from topic or stereotypes rather than fine-grained behavior.
6. **Rater familiarity**: original vs localized naming and anime exposure must be measured separately.
7. **Preexisting loader issue**: repo’s Copilot path still uses Sherlock/Poirot synthetic persona fixtures rather than their generated outputs; address in a *separate* study-readiness task.

## Integration notes
- `Persona` is an eight-field Pydantic model with `extra='forbid'`. This candidate validated locally against a mirror of the inspected schema.
- The current `prompts/extract_persona.md` asks for representative text examples; **do not run it on this summary corpus as though its `text` values were Kogoro's actual utterances**.
- Suggested repository layout for Codex review: `characters/kogoro/corpus/persona_corpus.jsonl`, `characters/kogoro/kogoro_persona_curated_candidate.json`, `characters/kogoro/metadata/...`, `tests/fixtures/kogoro_agent_response.txt`.
- Add character in `configs/characters.yaml` as `slug: kogoro`, `character_id: kogoro_mouri`, `display_name: Kogoro Mori`, only after user reviews this evidence candidate.
- Conversation UI already derives cards from the catalog; no redesign is required. Investigation support remains Sherlock/Poirot only. Verify four-agent mock and injected live-provider prompt loading; don't claim live testing if no provider call occurred.
- Before confirmatory study, independently inspect original manga pages for selected cases and document manga/anime differences; revise the corpus or register it as an adaptation-based candidate, then pre-register extraction/evaluation conditions.

## Dataset audit
- 36 records; 21 distinct directly referenced source IDs; 16 trait tags.
- Source counts: {'SHOG_BIRTHDAY': 1, 'SHOG_BLUECAT': 2, 'SHOG_REUNION': 2, 'SHOG_SCUBA': 1, 'SHOG_SELECTION': 2, 'SHOG_SUSPECT': 1, 'SHOG_UNSEEN': 1, 'TMS_CHARACTER': 1, 'VIZ_VOL09': 1, 'YTV_CHARACTER': 1, 'YTV_EP002': 2, 'YTV_EP003': 2, 'YTV_EP027_028': 3, 'YTV_EP114_115': 1, 'YTV_EP199_200': 1, 'YTV_EP305_306': 2, 'YTV_EP445': 2, 'YTV_EP529': 2, 'YTV_EP589_590': 3, 'YTV_EP911': 3, 'YTV_EP919': 2}
- Trait counts: {'attribution_boundaries': 7, 'care_and_loyalty': 9, 'cooperation': 4, 'defensiveness': 4, 'emotional_expression': 9, 'evidence_revision': 2, 'impulsiveness': 3, 'investigative_engagement': 7, 'investigative_reasoning': 8, 'observation': 2, 'practical_competence': 2, 'premature_conclusions': 3, 'pride_and_vanity': 4, 'professional_identity': 7, 'social_behavior': 7, 'uncertainty': 4}
- No byte-identical or punctuation-normalized duplicate records detected; thematic overlap remains possible and should be reviewed manually.
- There are **no claims of scientific recognizability, primary-manga authentication, or English dialogue-style fidelity**.
