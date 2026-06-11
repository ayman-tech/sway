# Sway Task Manager

**Description:** Read and manage tasks in the Sway task manager via its REST API. Supports listing active tasks, creating new tasks, completing tasks, and deleting tasks. Google Calendar tasks (read-only) are included in the task list.

**Publisher:** Sway

**License:** Private

**Use Case:** Personal productivity — let an AI agent view, create, and complete your tasks on your behalf.

**Setup:**
1. Open Sway → Settings → Sway API Key → Generate key
2. Copy the key and set `SWAY_API_KEY=sway_...` in your environment
3. Set `SWAY_API_URL` to your Sway API address (default: `http://localhost:8000`)

**Known Risks:**
- Write operations (create, update, complete, delete) are irreversible within Sway (soft-delete only). Always confirm with the user before executing write calls.
- The API key grants full read/write access to the user's tasks. Keep it secret and rotate via Settings if compromised.

**References:**
- [SKILL.md](SKILL.md) — full API reference and code examples
- [mcp.json](mcp.json) — MCP server configuration template

**Skill Output:** Task objects as JSON (id, title, description, status, due_at, due_date, source, created_at, updated_at)

**Ethical Considerations:** This skill accesses personal task data. Only deploy for the account owner. Do not store or share API keys.
