"""Narrow classification of non-JSON responses wrapped by PostgREST."""

from postgrest.exceptions import APIError


def retryable_gateway_status(exc: APIError) -> int | None:
    """Return a known gateway status, never infer it from a database message.

    postgrest.generate_default_error_message uses this exact message when the
    HTTP error body cannot be parsed as its JSON error schema. Its code is then
    the HTTP status, rather than a SQLSTATE or PGRST error code.
    """
    if exc.message != "JSON could not be generated":
        return None
    code = exc.code
    if isinstance(code, bool) or not isinstance(code, (str, int)):
        return None
    raw_status = str(code)
    if raw_status not in {"400", "502", "503", "504"}:
        return None

    # These are explicit gateway/service failures, even for empty/plain bodies.
    if raw_status != "400":
        return int(raw_status)

    # Do not turn arbitrary 400s into retryable failures. Match only the observed
    # Cloudflare HTML page. The SDK stores details as str(response.content),
    # so accept its bytes-repr prefix as well as plain HTML.
    if not isinstance(exc.details, str):
        return None
    body = exc.details[:8192].strip().lower()
    if body.startswith(("b'", 'b"')):
        body = body[2:].lstrip()
    if body.startswith(("<html", "<!doctype html")) and "cloudflare" in body:
        return 400
    return None
