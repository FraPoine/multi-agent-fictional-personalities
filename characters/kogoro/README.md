# Kogoro Mori conversation candidate — Sprint 8.4

Stable ID: `kogoro_mouri`; catalog slug: `kogoro`; display name: Kogoro Mori.
This is a **manually curated Persona candidate**, not LLM-extracted or
scientifically validated. The 36 original English editorial summaries in
`corpus/persona_corpus.jsonl` are behavioral descriptions, **not canonical
dialogue**. All six Persona examples are synthetic illustrations.

## Evidence and integrity

Corpus, Persona and research sidecars are imported byte for byte from the
supplied research package. `metadata/entry_provenance.json` maps every record
to `metadata/source_inventory.json`; example provenance is separate.
`metadata/methodology_and_qa.md` retains the research limitations.
Official publisher summaries and broadcaster synopses are reported sources;
original manga panels and dialogue were not independently verified. This
integration did not reauthenticate sources online. English voice choices and
confidence values are editorial judgments, not measured speech features or
calibrated probabilities. Assisted deductions must not be credited as entirely
independent reasoning, especially Conan's impersonation of Sleeping Kogoro.

All 10 external `SHA256SUMS` checks passed in the extracted research directory.
`metadata/research_SHA256SUMS` retains that historical manifest; names differ
here, so it is not a checksum command for this directory.
`metadata/integration_manifest.json` maps original names to imported files,
records their hashes and the archive hash, and documents these package issues:

- The unchanged `research_validation_manifest.json` has stale internal hashes
  for itself and `SHA256SUMS`. Use the externally verified manifest and the
  integration manifest for integrity checks.
- Contexts for `kogoro_0001` and `kogoro_0002` say “broadcaster”, whereas their
  source IDs and provenance identify `SHOG_SELECTION`, a publisher synopsis.
  The source inventory governs source type; original wording is retained.

## Runtime and limitations

The catalog registers Kogoro fourth, after Sherlock, Poirot and Layton.
Both conversation providers load `kogoro_persona_curated_candidate.json`
directly through the existing catalog path. The separate
`tests/fixtures/kogoro_agent_response.txt` is an original synthetic offline reply,
not a research corpus entry or live output. No special runtime or UI logic is
needed. Investigations remain restricted to Sherlock and Poirot.

Do not run the generic extraction prompt on these summaries as if they were
spoken lines. Summary-based manual curation differs methodologically from the
literary-dialogue approach for Sherlock/Poirot. Technical tests cannot establish
fidelity or recognizability. Independent source verification, aligned study
conditions and human evaluation remain future work. Sherlock/Poirot's existing
real-provider loading of synthetic catalog Personas is unchanged and outside
this integration's scope.
