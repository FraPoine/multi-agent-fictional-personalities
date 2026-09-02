# Sprint 7 demo-case integration completion

The three supplied English demos are available in the existing investigation
lobby. `data/raw/investigation/` remains provenance; application-ready YAML,
rich JSON, and image assets live under `configs/investigation/`.

The static/runtime and Lead/Visit boundaries remain intact. Eligible sections
are disclosed through `RevealedInformation` without duplication. Session state
contains only changing values. Lead-section effects are authoritative, so Demo
3 trigger notes in state metadata cannot double-apply.

Demo 1 supports floor/approach choices and the corrected canonical scope
`nw-32-top-floor`. Demo 2 supports A/B/C gates, revisit unlocks, explicit
break-in/uniform selection, and lead closure. Demo 3 supports time codes,
modes, budget changes, item-gated entries, and terminal outcomes.

Normal loading never opens solution or scoring files. Questions are retained
for later UI/scoring work but do not enter agent context. No network or API key
is required.
