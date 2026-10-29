# Writing a preset for another profession

A preset is a ready-made `jobsearch.config.yaml` with the profession knowledge filled in and every personal value empty.
The engine is neutral; a preset is where "what counts as a red flag in my field" lives. See `plugins/jobsearch/presets/qa/` for an example.

## Folder

`plugins/jobsearch/presets/<name>/` with `preset.yaml`, `facts.example.md`, `README.md`.

## Keys to fill

Start from `plugins/jobsearch/reference/config.template.yaml` (every key the loader knows) and fill:

- `honesty.tool_dictionary`: tools of your field; the grounding audit warns when a document names one that is absent from the master CV skills.
- `honesty.restricted_tools`: `pattern` (tools or languages the user must not claim as skills), `disclaimer_pattern` (words that make a mention honest), `cv_forbidden` (true keeps them off the CV).
- `honesty.never_claim`: `{pattern, why}` items for titles or claims common in your field that need proof.
- `blockers`: typed items, `keyword` and `domain` with `any`, `severity` (hard or soft) and a clear `label`. Mark them as examples.
- `letters.base_letters`: neutral archetype keys, not employer names.
- `targets`, `interview.redflag_checks`: optional field defaults.

Leave `identity` and everything personal empty. Never put a real name, employer, phone or email in a preset.

## Test it

1. Schema: `python3 scripts/datadir.py validate plugins/jobsearch/presets/<name>/preset.yaml` must exit 0 (unknown keys fail).
2. Merge: copy it to a scratch folder as `jobsearch.config.yaml` and run `python3 scripts/datadir.py show`; check that the dictionary and blockers are present.
3. Behaviour: run `python3 scripts/grounding_audit.py` on a sample letter that names a restricted tool with and without a disclaimer; the first must pass with a warning, the second must fail. Patterns may be double-quoted in YAML (`"\bword\b"`).
4. Add a test like `tests/test_preset.py` (merge plus a check that no personal value appears in the preset files).
