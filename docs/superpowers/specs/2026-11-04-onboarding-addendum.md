# Addendum: guided onboarding, general CV tune and help (`/jobsearch:jobsearch-setup`)

Status: APPROVED by the owner 2026-11-04. Plan and code follow; ships in 1.0.0 (§11).
Parent spec: `2026-10-27-jobsearch-plugin-design.md`; related: `2026-10-28-cv-tailor-addendum.md` (`/apply tune`). Decisions Q1-Q21 come from the owner's grilling session on 2026-11-04 and are cited as (Qn). Language rules (§3a) and the release number (§11) were set by the owner on 2026-11-04 after Q21; they replace the language parts of Q6 and Q8 and the version in Q20.

## 1. Intent
A new user should end setup with a working data folder: what they look for, their CV, the facts and master CV built from it, an ATS read of the CV, an agreed base cover letter and the links they want in letters. They should also always know what the plugin can do (§8). Every answer is saved in the user's data folder, changes only after the user confirms, and can be changed later.

## 2. Placement
- **`/jobsearch:jobsearch-setup`** gains a guided onboarding (§3) after the skeleton step it already does.
- **`/jobsearch:jobsearch-setup update`** works on an existing data folder. It shows the current answers and the steps still empty, and changes only what the user picks. Nothing is overwritten without confirmation (Q1).
  - A new or empty folder gets the full onboarding.
  - An existing folder gets `update` only.
  - The existing rule "setup never writes into an existing data folder" stays true for the skeleton step. `update` is the only way into an existing folder, and every write in it is confirmed.

## 3a. Languages (owner decision 2026-11-04)
- **The plugin is bilingual: Ukrainian and English.** `language.chat` is `uk` or `en`, and `datadir.py validate` accepts only these two values (empty = ask at setup). Every command and skill talks to the user in that language. Engine files in the repo stay English.
- **The CV is always English.** The uploaded CV, the master CV, `/apply tune` output and any targeted copy are in English. If the uploaded CV is not in English, setup asks for an English version and does not translate it, because a machine translation can change facts.
- **A cover letter is English or Ukrainian.** The existing cover-letter rule stays: the letter language equals the vacancy language.
  - A Ukrainian vacancy gets a Ukrainian letter; an English one gets an English letter.
  - For any other language (for example German), the plugin asks which of the two to use and suggests English.
  - Setup creates one base letter per language the user wants (EN, UA or both), as entries `base_en` and `base_uk` in `letters.base_letters`. `/apply` takes the one that matches the letter language.

## 3. Onboarding steps (in order; each can be skipped and done later with `update`)
1. **Language.** `language.chat` (`uk` or `en`) is taken from the user's first message and confirmed. The setup also asks which cover-letter languages the user needs: EN, UA or both (§3a).
2. **What the user looks for** (asked once; changeable with `update`):
   - primary roles into `targets.roles`. Selective and not-primary roles are left to `update` (Q15).
   - country (`targets.country`: any | ukraine | not_ukraine).
   - remote (`targets.remote`: any | yes | no).
   The default is `any` for both.
3. **Optional limits** (skippable; Q7): minimum salary with currency and net/gross, schedule end, and hard "no"s such as a coding challenge. These go into typed `blockers`. Without them `/rank` says "no blockers configured".
4. **CV, in English** (§3a). One final CV in the first version (Q9; `paths.cv_files` is already a list, so a second CV comes through `update`).
   - Formats: PDF, read by Claude, or pasted text. For DOCX the user is asked to export a PDF. No new dependency (Q3).
   - The file is stored in the data folder and listed in `paths.cv_files`. It is read-only from then on (hard rule 6).
5. **Identity.** Name, emails, phones and handles are read from the CV. They are written to `identity.*` after the user confirms them (Q5), and the setup checks that the publish gate now has patterns.
6. **Facts and master CV** (built once, create-only; Q2, Q12, Q13):
   - `paths.facts`: employers, dates, titles, skills, education and languages from the CV, plus an empty gap table. Each unclear or conflicting item is asked, never guessed (hard rules 3 and 4).
   - `paths.master_cv`: the CV content as labelled lines. Labels are generated, for example `[EXP-1-2]` (job 1, bullet 2) or `[SKILL-3]`. The user reviews them before the file is created.
   - One question: "Is anything in this CV something you do not want to claim in letters?" The answers go into `honesty.known_risk_lines` or `honesty.never_claim` (Q13).
7. **Numbers.** Every metric in the CV is listed. The user confirms each one, and the confirmed ones go into `honesty.allowed_numbers` (Q4). An unconfirmed number never reaches a letter or a tuned CV. This is what keeps the grounding audit from FAILing on the user's own real results.
8. **ATS read.** Right after the first CV, the setup runs `ats-screening` Stage 1 automatically (score and parsing risks) and reports it. It then offers the general tune from §4. Any rewrite happens only after the user says yes (Q11).
9. **Base cover letter.**
   - A draft is built from the facts and the target roles, one per chosen letter language (EN and/or UA; §3a).
   - It passes `grounding_audit.py --kind letter` and the `grounding-audit` skill before it is saved. A draft with an open FAIL is not saved (Q16).
   - The agreed text goes to `paths.letter_kb` and `letters.base_letters`. `/apply` adapts it per vacancy.
10. **Links.** The user is asked which links go into letters: GitHub, LinkedIn, portfolio, all or none. They are stored in the new key `identity.links` (§5). Only the URL format is checked; the setup does not open them (Q14).
11. **Done.** The setup summarizes what was saved and what was skipped, and points to `/jobsearch:help` (§8).

## 4. General CV tune: `/apply tune` without a vacancy (Q10)
- **With a vacancy:** unchanged from the cv-tailor addendum.
- **Without one:** the target is not a single vacancy. It is the target roles (`targets.roles`) plus the keywords that recur in 2 or more files of `paths.ranked`. The steps are the same: Stage 1 instead of Stage 2 for the score, the same report format, the same guardrails (no keyword stuffing, no tools without evidence), the same `--kind cv` audit and no-overwrite rules.
- **Output:** `<paths.reports>/cv_tune_general_<YYYY-MM-DD>.md` with its `_bullets` file and audit file. A targeted copy is built only when the user asks.
- **No ranked vacancies yet** (a new user): it uses the target roles only, and says so.

## 5. Config keys
- **New: `identity.links`**, a list such as `[{label: "GitHub", url: "https://..."}]`. Letters and the LinkedIn skill read it. It is an identity value, so the publish gate treats each URL as a private pattern.
- **Reused:** `targets.roles`, `targets.country`, `targets.remote`, `blockers`, `honesty.*`, `letters.base_letters` (entries `base_en` / `base_uk`), `paths.*`.
- **Narrowed:** `language.chat` accepts only `uk`, `en` or empty (§3a).
- **No other new keys.**

## 6. Guard hook change: create-only for the master CV (Q2)
`hooks/guard_writes.py` today denies every write to `paths.master_cv` and asks before edits of `paths.facts`. After this change:
- **Master CV:** a Write to `paths.master_cv` when the file does not exist yet becomes **ask** (the user confirms creation). An Edit, or a Write over an existing file, stays **deny**.
- **Facts and tracker:** unchanged.
- **Final CV files:** writing a new file into `paths.cv_files` during setup is a copy of the user's upload. That is also create-only with **ask**, and overwriting stays **deny**.

## 7. Session-start reminder (Q21)
In the data-folder project, the SessionStart hook checks for missing onboarding pieces: no CV in `paths.cv_files`, no master CV, no base letter, empty `identity.links` (when the user did not answer "none"), or empty `targets.roles`. It lists the missing steps once per session start and points to `/jobsearch:jobsearch-setup update`. When nothing is missing it says nothing extra. The commands-and-skills overview from 0.4.0 stays as it is.

## 8. Help
`/jobsearch:help` already exists (0.4.0). It lists every command with its modes and every skill from their own descriptions, the usual workflow and the setup status. With this addendum:
- **Setup status:** "Setup status" also lists the missing onboarding steps from §7, so help answers "what can I do" and "what is left to set up".
- **New modes appear on their own:** help reads the descriptions, so `jobsearch-setup update` and `apply tune` without a vacancy show up there automatically, as long as the descriptions name them.
- **Pointers:** the onboarding's last step and the session-start reminder both point to `/jobsearch:help`.

## 9. Hard-rule interplay
- **Rule 1:** nothing is sent or posted.
- **Rule 3:** facts come only from the user's CV and answers; NOT IN SOURCES otherwise.
- **Rule 4:** conflicts in the CV are asked.
- **Rule 5:** every config and data change is confirmed; `update` never overwrites silently.
- **Rule 6:** the uploaded CV is read-only after it is stored; the master CV is created once and never rewritten (§6).
- **Rule 7:** setup fetches nothing.

## 10. Changes to the parent spec (Q19)
- **Non-goal, current:** "No new CV builder. CV files are the user's data; the engine analyzes and audits them and, in `/apply tune`, suggests grounded edits..."
- **Non-goal, proposed:** add "During setup the engine creates the master CV once from the user's CV (create-only, after the user confirms) and never rewrites it. The final CV files stay read-only."
- **§3.4:** add `identity.links`.
- **§6.6 (Setup):** points to this addendum.

## 11. Release (Q20)
**1.0.0, the first public release** (owner decision 2026-11-04). It ships after all open edits are done: this onboarding, the general tune, the help and session-start updates and the bilingual rules, together with the already merged `/rank` location filter, the egress guard (`2026-11-04-egress-guard-addendum.md`) and the portal scanner A1 (`2026-11-04-portal-scanner-addendum.md`, off by default). No 0.5.0 in between; the CHANGELOG section `0.5.0 (unreleased)` becomes `1.0.0`.

## 12. Verification (Q17)
- **Doc tests:**
  - the language rules of §3a are in `jobsearch-setup.md` and the cover-letter skill, and `datadir.py validate` rejects a `language.chat` other than `uk`, `en` or empty;
  - `jobsearch-setup.md` names every step of §3 in order, plus the `update` mode, the create-only rule and the audit before the base letter is saved;
  - `apply.md` documents tune without a vacancy;
  - `help.md` names the missing-steps status.
- **Unit tests:**
  - guard create-only: create = ask, overwrite or edit = deny, for the master CV and the CV files;
  - `identity.links` in the schema and validation;
  - the publish gate picks up link URLs;
  - the session-start missing-steps list: present when something is missing, silent when complete.
- **Manual checklist** on the synthetic persona (Jordan Example): a full onboarding on a new folder, and `update` on the fixture folder.
- **Live check by the owner:** one onboarding on a new folder.
