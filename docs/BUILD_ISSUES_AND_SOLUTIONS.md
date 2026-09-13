# Real-World Engineering Challenges in Sway

This document summarizes the main product and production-engineering problems addressed while building Sway. Each solution reflects the implemented architecture and is phrased as an interview-ready explanation of the problem, trade-off, and result.

## 1. Protecting Sensitive Integration Credentials

**Problem:** Google OAuth client secrets, refresh tokens, and Sway API keys are highly sensitive; storing them as plaintext would allow a database leak or accidental log exposure to become an account compromise. The application also needed a safe way to refresh Google access without asking the user to reconnect repeatedly.

**Solution:** We encrypt recoverable secrets at rest with Fernet using a server-managed `GOOGLE_CREDENTIALS_ENCRYPTION_KEY`, and decrypt them only inside the API when needed. API keys also have a SHA-256 hash for authentication, while logs and diagnostic middleware deliberately exclude tokens, request bodies, and user data.

## 2. Keeping Every User's Data Isolated

**Problem:** Sway is a multi-user application, so relying only on frontend filtering could expose one user's tasks, settings, or calendar connection to another user. Privileged backend operations also needed to remain separate from ordinary user requests.

**Solution:** Every protected API route validates a Supabase JWT or Sway API key and creates a user-scoped request context. Supabase Row-Level Security restricts normal task and settings operations to `auth.uid() = user_id`, while service-role access is kept server-side and used only for narrowly defined operations such as encrypted integrations and expiring public shares.

## 3. Synchronizing Google Calendar Without Corrupting User State

**Problem:** Calendar events can be renamed, rescheduled, converted between timed and all-day events, or deleted in Google after being imported into Sway. A naive overwrite could also erase Sway-specific state such as whether the user completed an imported event or configured a local reminder.

**Solution:** We made Google Calendar the source of truth for imported event content and kept the integration deliberately read-only: Sway never edits or deletes the original Google event. Stable IDs derived from the user and Google event ID let imports update the same task, while mapping preserves Sway-owned completion and reminder state; cancelled or missing Google events become soft-deleted Sway tasks.

## 4. Making Incremental Calendar Sync Recoverable

**Problem:** Re-fetching every calendar event on every visit is slow and wasteful, but incremental sync tokens can expire or miss a deletion after an interrupted synchronization. Concurrent sync requests can also duplicate work and compete with page-loading requests.

**Solution:** We persist a sync token per selected Google calendar and request only changes after the first bounded full import. If Google returns `410 Gone`, the token is discarded so the next pass performs a full import, which reconciles events missing from the import window; a server lease, five-minute cooldown, and client in-flight guard prevent overlapping sync jobs.

## 5. Resolving Offline and Multi-Device Editing Conflicts

**Problem:** The desktop application must remain useful without a network connection, while the same account may also change tasks from the web or another device. Retrying writes without conflict rules can lose changes, duplicate them, or create an endless upload/download loop.

**Solution:** Desktop writes are committed to SQLite immediately and marked with pending synchronization state, then pushed to Supabase when connectivity returns. Cloud timestamps are assigned by the database, newer records win during pulls, and a 60-second overlap around the last pull watermark prevents edge-timed updates from being skipped without repeatedly applying unchanged rows.

## 6. Propagating Deletions Across Devices

**Problem:** Hard-deleting a task removes the evidence needed to tell another offline device that the record was deleted. That device could later upload its stale copy and unintentionally recreate the task.

**Solution:** Sway uses soft deletion by setting `deleted_at` and updating the record's synchronization timestamp. These tombstones flow through the same synchronization path as other changes, allowing offline clients to apply the deletion consistently while preserving recovery and conflict information.

## 7. Handling Dates, Time Zones, and Recurrence Correctly

**Problem:** Timed tasks, all-day tasks, daylight-saving changes, and recurring schedules behave differently across user time zones. Treating them all as naive timestamps can move an event to the wrong day or shift a recurring task after a daylight-saving transition.

**Solution:** All persisted timed values are timezone-aware UTC values, while each UI converts them to the user's local zone for display and editing. All-day dates remain date values, and recurring timed tasks retain their recurrence timezone so occurrences are generated in local wall-clock time before being converted back to UTC.

## 8. Preventing Dashboard and Supabase Worker Stalls

**Problem:** Opening the dashboard after a long idle period could trigger concurrent page queries and Google synchronization while every request created new Supabase clients and remotely validated the same JWT. Slow upstream calls accumulated in the API thread pool, leaving the interface stuck on “Loading tasks…” and occasionally causing worker replacement.

**Solution:** Foreground queries now finish before Google sync begins, and each worker reuses a bounded HTTP connection pool instead of rebuilding connections per request. Supabase JWTs use supported local claims verification when possible, upstream timeouts return retryable `503/504` responses, and Uvicorn keeps two workers with a longer health-check timeout.

## 9. Diagnosing Production Failures Without Exposing Private Data

**Problem:** A generic Caddy `502` or a dead worker does not reveal whether the delay occurred during authentication, a Supabase query, task grouping, or Google import. Adding unrestricted debug logging would create a new security and privacy risk.

**Solution:** We added generated request IDs, process IDs, status codes, total durations, and correlated stage timing around the important external and computational operations. `X-Request-ID` and `Server-Timing` headers connect browser observations to server journals, while the custom diagnostics record only the method and route path—not query strings, authorization tokens, bodies, or user content.

## 10. Preserving Useful UI State During Network Failures

**Problem:** Replacing already loaded tasks with a blank spinner during every refetch makes a temporary network problem look like data loss. An indefinite loading message also gives the user no recovery path when a request will never complete.

**Solution:** The first load uses an accessible skeleton, an automatic transient retry is shown as “Reconnecting…”, and a terminal error provides a manual Retry action. During background refreshes, TanStack Query keeps existing in-memory task data visible and shows “Syncing…” or “Couldn't refresh” without suggesting that offline mutations have been saved.

## 11. Designing a Responsive Dashboard for Real Mobile Use

**Problem:** Shrinking the desktop sidebar onto a phone consumed most of the viewport, obscured content, and created poor touch targets. Data-dependent content such as long calendar titles and URLs could also change the layout after the initial render.

**Solution:** Below the desktop breakpoint, Sway uses a dedicated mobile shell with a compact header, bottom navigation, an accessible More sheet, safe-area spacing, and a floating task action. Calendar columns use explicit `minmax(0, 1fr)` sizing and overflow containment, while mobile sheets, cards, and controls maintain touch-friendly sizing without changing the desktop experience.

## 12. Adding PWA Installation Without Caching Private Data

**Problem:** Users wanted an app-like installation experience, but caching authenticated pages or API responses in a service worker could expose stale tasks, tokens, or another user's data on a shared device. Full offline editing would also require a much larger conflict-resolution system.

**Solution:** We implemented an online-first PWA with a manifest, branded icons, standalone launch behavior, production-only service-worker registration, and an installation card in Settings. The service worker caches only the offline document and public icon assets; it bypasses API calls, Supabase, authenticated page data, non-GET requests, and all mutations.

## 13. Sharing Availability Without Publishing Account Data

**Problem:** Public availability links must work without authentication, but exposing a database row ID or a guessable token could reveal a user's identity or schedule. Old links also need to stop working without requiring manual cleanup.

**Solution:** We generate cryptographically random, human-readable share tokens but store only their SHA-256 hashes, so the original public token cannot be recovered from the database. Shares contain a limited snapshot rather than live account access, expire after seven days, are capped per user, and are read through a server endpoint instead of a public Supabase policy.

## 14. Sharing Domain Behavior Across Desktop and Web

**Problem:** Implementing task rules independently in PySide6, FastAPI, and Next.js would allow recurrence, Google mapping, grouping, and reminders to behave differently depending on the client. Fixing the same rule in several places would also increase regression risk.

**Solution:** We extracted canonical task models and reusable scheduling, recurrence, reminder, and Google-event mapping logic into `packages/core`. The desktop and API consume the same Python domain functions, while the web stays behind the API contract instead of duplicating persistence rules in the browser.

## 15. Deploying Reliably to a Small VM

**Problem:** A real deployment needs repeatable builds, automatic restarts, TLS termination, and a safe way for CI to update the application. Paths, SSH identity, environment variables, or service commands that exist only in an interactive shell commonly fail under GitHub Actions or systemd.

**Solution:** We use GitHub Actions to connect with a dedicated SSH key and run a repository-owned deployment target from an explicit absolute path. Caddy terminates HTTPS, systemd owns the API and web processes with restart policies, and production environment files remain on the VM rather than being stored in the repository or CI logs.

## Interview Talking Points

- Explain the ownership boundary in Google sync: Google owns event content; Sway owns local completion and reminder state.
- Emphasize why soft deletion is a synchronization feature, not just a recovery feature.
- Describe why the desktop can be offline-first while the PWA is intentionally online-first.
- Discuss the security boundary between user-scoped RLS access and narrowly scoped server service-role access.
- Use the worker-stall investigation as an observability example: evidence led to request coordination, bounded waiting, and correlated timing rather than speculative caching.
