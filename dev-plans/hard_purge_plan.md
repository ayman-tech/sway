Goal: keep the DB clean by physically deleting old completed tasks. Storage isn't urgent (500 MB ≈ decades), so this is "when distributing," not now.

Lifecycle:

Day 0: completed → in Completed view
Day 30: soft-delete (tombstone) → leaves all views (already implemented)
Day ~150 after tombstone (≈180 post-completion): hard-delete
Mechanism — deterministic purge run everywhere (no deletions feed needed for completed tasks):

Cloud — pg_cron daily:

delete from public.tasks
where deleted_at is not null and deleted_at < now() - interval '150 days';
Each device — same rule as a hard DELETE locally, run before push in the sync cycle.
Because the rule is deterministic + time-based, cloud and every device converge with nothing to propagate → no resurrection of completed rows.
Decisions locked in:

Keep in-place un-complete (status flip). The "un-complete spawns a new task" idea was rejected — the old row still shows in Completed unless you tombstone it, which just reintroduces the problem.
Don't hard-purge user-delete tombstones (deletes of active tasks are rare/tiny) — just keep them. Avoids needing a deletions feed at all.
Edge cases / safety:

Resurrection needs a device offline >150 days continuously with a pending edit — mitigated by the huge margin + each device self-purging old completed rows before pushing.
Editing a >150-day completed task offline → that edit is dropped on reconnect (rare, fine).
The one residual (ultra-stale device showing a stale active task the other device deleted) → add a resync valve later if it ever bites: if last_pull_at is older than the margin, do a full re-pull and drop local rows missing from the cloud set.
Prereqs (already done): #1 server-set updated_at trigger, #2 60s pull overlap, #4 deterministic recurring-completion id.