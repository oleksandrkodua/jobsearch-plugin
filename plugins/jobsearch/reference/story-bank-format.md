# Story bank format (STAR+R)

File: `paths.story_bank` (default `interview/story_bank.md`). Read by `/interview`. One story per `## <id>: <title>` block, ids `S-001`, `S-002`, ... never reused.

## Fields (all required)

| Field | Content |
|---|---|
| id | `S-NNN`, in the heading |
| title | Short name, in the heading after the id |
| Source | The master CV label or the row of the facts file the story rests on. No source = the story cannot be added |
| Tags | Competencies, comma separated (for example `reliability, testing, teamwork, conflict, ownership`). `/interview` maps questions to stories by tag |
| Last used | Vacancy id and stage (for example `VAC-001 / technical`), or `never` |
| Situation | Context, one or two sentences |
| Task | What the user had to achieve |
| Action | What the user did personally (not the team) |
| Result | Only confirmed numbers. If no number is confirmed, write `no number, observed effect:` and the effect the user saw |
| Reflection | What the user learned or would do differently (the "R" in STAR+R) |

## Rules

- Stories enter the bank only with the user's approval, one story at a time, after the user has read the exact text. `/interview` may propose a story; it never saves one unasked.
- Facts only from the user's profile or from what the user states in chat. Never invent a number, a team size or an outcome; a missing detail is `NOT IN SOURCES`, ask the user.
- Changing a saved story (a new number, a new tag) also needs the user's approval. Never delete or overwrite a story without two separate confirmations.
- Target size: 5 to 10 master stories that can be re-angled by tag for different questions. More is not better; a story used in every interview is a good story.
- A story must not claim more than the submitted CV and letter claim.
