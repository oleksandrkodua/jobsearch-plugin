---
name: cover-letter
description: Cover letters for the user's own job applications. Use when the user asks for a cover letter, application letter, motivation letter, or answers to application form questions for a specific vacancy. Works strictly from the facts file, the master CV and the letter knowledge base named in the config; invents nothing and never sends. Not for CV scoring (use ats-screening), not for fact-checking a finished text (use grounding-audit) and not for tracker updates (use outcome).
---

# Cover Letter

This file describes the order of work for letters. It does not duplicate the user's knowledge base; it points to it through the config. Read `${CLAUDE_PLUGIN_ROOT}/reference/hard-rules.md` first, then the config (data dir: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" show`). The user sends every letter; you only draft.

## Sources of truth, highest priority first
1. The corrections file in `paths.letter_kb` (facts corrected after the base letters were written), if the user keeps one.
2. The base-letter file in `paths.letter_kb` (texts of all letters named in `letters.base_letters`).
3. The user's CV: experience, stack, dates (`paths.master_cv`, `paths.facts`).
4. The process and style rules file in `paths.letter_kb`.
5. The application log in `paths.letter_kb` (what is already sent, so it is not regenerated).

When sources conflict, do not pick the convenient one silently. Show the conflict and ask.

## When to use
A letter for a specific vacancy, an adaptation of an existing letter, answers to application form questions. Not for tracking statuses (that is the `/outcome` command).

## Order of work
1. **Check the input.** If only a link or a title is given with no description, ask for the full text. Do not guess.
2. **Parse the vacancy.** Title, domain, must-have vs nice-to-have, red flags, location requirements.
3. **Pick the base letter** from the keys in `letters.base_letters`. If the vacancy domain matches none, use the first key marked as general, or ask the user. If the list is empty, say "no base letters configured" and write from the CV and facts alone.
4. **Match against facts.** Strong matches and gaps separately. A gap is either addressed honestly or not mentioned. Never filled with invention.
5. **Write the letter**, adapting the base text. Base texts are a style reference, not blocks to copy-paste: do not move passages verbatim between letters of one batch.
6. **Self-check** against the checklist below.
7. **Run the `humanizer` skill**: draft, self-check "what gives away AI text", final rewrite.
8. **Run the `grounding-audit` skill** (script pass, then the semantic pass) before hand-over.

## Hard prohibitions
- Do not invent skills, tools, metrics or projects beyond the CV and the knowledge base.
- Do not claim as personal hands-on skill any tool that the master content does not confirm. A tool named in a vacancy analysis as a "match" is not confirmation.
- Respect every `honesty.never_claim` entry and `honesty.restricted_tools`: a restricted tool may appear only with the disclaimer the config describes, and only where `cv_forbidden` allows.
- Never repeat a line from `honesty.known_risk_lines`.
- Describe domains and roles only as the facts file words them. No title, people management or hiring claim without a facts row.
- Draw an honest line between real experience and full expertise in an adjacent field (AI, automation, management).
- Never lie about an employer. Nothing about private life or protected characteristics.

## Style
- Length `letters.words_min` to `letters.words_max` words unless the vacancy asks otherwise.
- The voice of a working professional, not marketing copy. Short sentences, concrete detail.
- None of `letters.forbidden_buzzwords`. Never open with any of `letters.forbidden_openers`.
- Salutation: `letters.salutation`; if empty, address the hiring team or the named contact. Put the company name on the addressee line at the top.
- Sign-off lines from `letters.signature_lines`; if empty, a plain closing and the user's name from `identity`.
- If `letters.no_long_dash` is true, use no long dash anywhere; a short hyphen with spaces only.
- The letter language equals the vacancy language. If correspondence with the recruiter was in another language, ask before writing.
- Vary openings and the way gaps are admitted inside one batch, so the letters do not read as a template.

## Part-time vacancies
Open with direct framing: there is capacity next to the main job and an interest in the domain. Mark such vacancies separately from full-time ones in the list.

## Output format
Per vacancy:

```
## Vacancy analysis
- Key requirements:
- Strong matches:
- Gaps: (or "no significant gaps")

## Cover Letter
[full text]

## Alternative opening
[one spare hook]
```

A batch goes out as one file, plain text or markdown, all letters together. Each letter body is one compact block without blank lines between paragraphs, so it pastes into an application form field. Separate PDFs only on explicit request; the plugin ships no PDF renderer, so say so and offer a text file.

## Checklist before hand-over
1. Every fact traces to the CV, the facts file or the corrections file.
2. No prohibited wording from the section above.
3. The opening is not a template; the gap is handled honestly.
4. Word count in range, no buzzwords.
5. No long dash when the config forbids it.
6. Language matches the vacancy.
7. Deal-breaker questions, such as location or schedule, are raised openly, not passed over.
8. The application log shows the vacancy is not in a closed batch.
9. `humanizer` and `grounding-audit` done. Say clearly: "not sent".
