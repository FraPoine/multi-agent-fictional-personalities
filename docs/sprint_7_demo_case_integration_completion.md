# Sprint 7 demo-case integration completion

The three supplied English demos are available in the existing investigation
lobby. `data/raw/investigation/` remains provenance; application-ready YAML,
rich JSON, and image assets live under `configs/investigation/`.

The static/runtime and Lead/Visit boundaries remain intact. Eligible sections
are disclosed through `RevealedInformation` without duplication. Session state
contains only changing values plus an auditable accounting ledger. Lead-section
effects are authoritative, so redundant Demo 3 trigger metadata is absent from
runtime configuration and cannot double-apply. Authored actions are preflighted
before visits or charges, and authored outcomes complete without `FinalTheory`.

Demo 1 supports floor/approach choices and the corrected canonical scope
`nw-32-top-floor`. Demo 2 supports A/B/C gates, revisit unlocks, explicit
break-in/uniform selection, and lead closure. Demo 3 supports time codes,
modes, budget changes, item-gated entries, and terminal outcomes. Demo 3 charges
each successful configured variant visit, including a revisit in another
available variant; failed preflight actions create no visit and no charge.

Normal loading never opens solution or scoring files. Questions are retained
for later UI/scoring work but do not enter agent context. No network or API key
is required.
