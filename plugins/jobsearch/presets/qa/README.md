# QA example preset

An example configuration for a manual QA job search. It is an example, not a default: the engine itself
makes no QA assumptions, and nothing here is applied unless you copy it.

What is inside:

- `preset.yaml`: a full valid config. It carries a QA tool dictionary, a restricted-tools rule (automation tools and languages
  may appear in a letter only next to a disclaimer word and never on the CV), example keyword and domain blockers,
  and neutral letter archetype keys. All identity and personal values are empty.
- `facts.example.md`: a facts skeleton with a gap table.

How to use it in your data folder (the folder `JOBSEARCH_DATA_DIR` points to):

1. Run `/jobsearch-setup` and pick the `qa` preset, or copy by hand: `cp preset.yaml "$JOBSEARCH_DATA_DIR/jobsearch.config.yaml"`
   and `cp facts.example.md "$JOBSEARCH_DATA_DIR/profile/facts.md"`. Never overwrite an existing config.
2. Fill `identity`, `targets`, `letters` and `honesty.allowed_numbers` with your own values.
3. Edit or delete the example blockers.
4. Check it: run `/jobsearch:jobsearch-setup` (it validates the copy), or run the plugin's `scripts/datadir.py` with `validate "$JOBSEARCH_DATA_DIR/jobsearch.config.yaml"`.

To build a preset for another profession, see `docs/presets.md`.
