# Web Push rollout

Push is optional. Without its configuration, the rest of Sway still works. This
release sends task titles to opted-in devices, not descriptions/links. Delivery
is best effort, not an exact-time alarm. iOS 16.4+ requires a Home Screen install.

## One-time setup

1. Back up the database, then run `supabase/migrations/20261004_web_push.sql` in
   Supabase SQL Editor. This is required even for a fresh `schema.sql` install.
   The new tables/functions are service-role-only; no JWTs are stored in them.
2. Install the committed dependencies with `uv sync --project apps/api --frozen`.
3. Generate VAPID keys **once**, locally or on the VM:

   ```bash
   uv run --project apps/api python -c 'import base64; from cryptography.hazmat.primitives.asymmetric import ec; from cryptography.hazmat.primitives import serialization as s; k=ec.generate_private_key(ec.SECP256R1()); enc=lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode(); print("WEB_PUSH_PRIVATE_KEY="+enc(k.private_bytes(s.Encoding.DER,s.PrivateFormat.PKCS8,s.NoEncryption()))); print("WEB_PUSH_PUBLIC_KEY="+enc(k.public_key().public_bytes(s.Encoding.X962,s.PublicFormat.UncompressedPoint)))'
   ```

4. Save those values and `WEB_PUSH_SUBJECT=mailto:YOUR_REAL_CONTACT_EMAIL` in the
   API environment (`apps/api/.env` or the root `.env`). Do not commit or paste
   the private key in logs/issues. Back it up in a password manager; keep the
   same keys across deploys. The public key is fetched through the API, not baked
   into the web build. `SUPABASE_SERVICE_ROLE_KEY` is required as before.
5. Deploy API and web via the existing GitHub artifact workflow. No web build on
   the VM is needed. Verify the ordinary dashboard still works.
6. Copy `deploy/sway-push.service` to `/etc/systemd/system/sway-push.service`.
   Before enabling it, edit **User**, **WorkingDirectory**, and both paths in
   **ExecStart** to your VM account and repository path. Run exactly one worker
   service; do not launch it inside Uvicorn.

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now sway-push
   sudo systemctl status sway-push --no-pager -l
   sudo journalctl -u sway-push -n 30 --no-pager
   ```

Normal deployments restart the worker only if it is installed and enabled;
customized systemd files are never overwritten. `make push` runs a local worker;
the database lease prevents competing workers sending concurrently. Test against
a separate Supabase project where possible.

## Verification

- Use a production web build/HTTPS (or localhost) because dev mode does not
  register the service worker. Open Settings → Notifications on this device.
- Enable and send a test. “Accepted” means the provider accepted it, **not** proof
  that the OS displayed it. Test on Android Chrome, an iPhone Home Screen app,
  and desktop. Check denied permission and device Focus/battery settings.
- Create a timed task a few minutes ahead, close Sway, and check the title/body
  and click behavior. Test an advance reminder and a recurring task too.
- Complete/delete/reschedule a task before its reminder. Verify it is not sent
  at the old time. Repeat with two tabs and two devices; each enabled device
  should receive one notification per scheduled reminder.
- Sign out, then sign in as another user. Old queued pushes must not show the
  former user's task title. Enabling is explicit for the new account.
- Stop the worker briefly and restart. It catches up at most ten minutes and
  never sends reminders older than device enrollment. Disable/re-enable on a
  device to test expired registrations.
- Observe `push heartbeat` counts and `cycle_failed` exception types. Logs omit
  endpoints, keys and titles. Table `accepted_at` records provider acceptance.

Measure the e2-micro while exercising the dashboard:

```bash
sudo systemctl show sway-push -p MemoryCurrent -p CPUUsageNSec -p NRestarts
ps -eo pid,ppid,%cpu,rss,args --sort=-rss | head -15
free -h
vmstat 1 10
sudo journalctl -u sway-push --since '-15 minutes' --no-pager
curl --max-time 10 -sS -o /dev/null -w 'health=%{http_code} total=%{time_total}s\n' http://127.0.0.1:8010/health
```

Polling is once per minute, sends are sequential with bounded connect/read
timeouts, and queries are paginated. At healthy low load, target provider
submission within roughly 60 seconds, not a delivery-time guarantee. Check
dashboard request timings before/after; do not assume a fixed RAM cost.

## Limitations and rollback

- Recurrence uses the shared UTC/timezone rules. All-day tasks do not push.
  Google tasks need an explicit reminder and use the last imported event state;
  the worker does not initiate Google sync.
- Delivery is at-least-once under ambiguous network failures. Durable identities
  and stable notification tags reduce duplicates; exact-once display is not
  promised. Retries expire ten minutes after the scheduled reminder.
- Subscription metadata and the local account binding are sensitive. The local
  IndexedDB contains only identifiers, never tasks or session tokens. Revocation
  clears the binding first. A push already in flight may display a generic
  settings message after logout, but not the previous account's title.
- Rotate VAPID keys only deliberately: stop the worker, have users disable old
  device enrollments, replace keys, restart API/worker, then re-enroll devices.
  Existing subscriptions cannot simply be signed with a different key.
- Roll back by `sudo systemctl disable --now sway-push`, remove/blank the three
  push environment values, and restart `sway-api`. Keep the additive tables and
  migration; do not delete task data. Devices can disable push in Settings and
  explicitly enable foreground-only reminders. Stop/enrollment disabling cannot
  retract notifications already accepted by a provider.

Tests: `cd apps/api && uv run --with pytest python -m pytest`;
`cd packages/core && uv run --with pytest python -m pytest`;
`npm --prefix apps/web run test:push`; `npm --prefix apps/web run typecheck`;
`make build-web`. The repository's legacy `next lint` script is unsupported by
Next.js 16; it needs a separate ESLint configuration migration.
