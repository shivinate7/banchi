"""The request refusal every route module can raise, and the one parser for a box number in a body.

`BadRequest` lived in `server/capture_server.py`, which imports `server/codes_routes.py`, so the
codes routes could not raise it and kept a parser of their own (DEBT86). It lives here now and
`capture_server.BadRequest` is this class. `require_box` is the one box-number parser.
"""

from __future__ import annotations

from http import HTTPStatus


class BadRequest(ValueError):
    """A request this server refuses, carrying the status and code to answer with."""

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def require_box(payload: dict, field: str = "box", missing: str = "Send a box number.") -> int:
    """A box number from `payload[field]`: `<field>_required` when absent, `<field>_invalid`
    when it is not a whole number or is below 1."""
    raw = payload.get(field)
    if raw is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, f"{field}_required", missing)
    try:
        box = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, f"{field}_invalid", f"{field} was {raw!r}; send a whole number."
        ) from None
    if box < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, f"{field}_invalid", f"{field} was {box}; boxes start at 1."
        )
    return box
