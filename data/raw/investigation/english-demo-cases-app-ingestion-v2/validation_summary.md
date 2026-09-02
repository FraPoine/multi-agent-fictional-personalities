# Global validation summary

Status: **PASS**

Repository boundary checked at commit `bbc30ef0979574f50853dbcb3518e69892c254b9` (current `main` during preparation).

- Cases processed: 3
- Strict current-app YAML accepted by `CaseDefinition.model_validate`: 3/3
- Temporary catalogue accepted by `load_case_catalog`: yes
- Current-app resources resolved: 9/9
- Rich physical lead files: 18 + 26 + 18 = 62
- Demo 3 playable mode variants: 32
- Rich assets present and safe: 9/9
- Cross-file case IDs, London lead keys/references and schemes: pass
- Flag declaration/use checks: pass
- Spoiler/ground-truth key scan outside `spoilers/`: pass

Known source issues are preserved rather than guessed: Demo 1’s printed scoring arithmetic conflict is marked for review; Demo 2’s uniform choice is assigned to 68 WC according to visual layout; Demo 3 requires a new `time-code` scheme and mode-aware rich-content loader.

Machine-readable results are in `validation_checks.json`.
