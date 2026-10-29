# Status vocabulary (valid values for vacancies.csv)

ACTIVE        HR/interview/test task in progress (only with real movement)
APPLIED       application sent, waiting (auto-replies do not make it ACTIVE)
NO_RESPONSE   application sent, silence (ignored); set by the user's ruling, never automatically
REJECTED     employer said no
DECLINED      the user declined / withdrew
CLOSED        vacancy closed or ended, no known employer rejection or self-decline
SKIPPED       evaluated, deliberately not applied
NOT_APPLIED   evaluated, decision pending (not applied yet)
DO_NOT_APPLY  evaluated, hard no
UNKNOWN       sources conflict or no information. Never guessed: see proposed_status/review_reason

Rules: ACTIVE only with a real HR interview or next step (test task, interview). Auto-replies = APPLIED.
UNKNOWN rows carry `proposed_status` and `review_reason`; the user decides, nothing is guessed.
