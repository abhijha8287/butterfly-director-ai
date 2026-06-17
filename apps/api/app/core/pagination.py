import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, or_

from app.core.exceptions import ValidationError

_CURSOR_SEPARATOR = "|"


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = f"{created_at.isoformat()}{_CURSOR_SEPARATOR}{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        created_at_raw, row_id_raw = raw.split(_CURSOR_SEPARATOR)
        return datetime.fromisoformat(created_at_raw), UUID(row_id_raw)
    except (ValueError, binascii.Error) as exc:
        raise ValidationError("Invalid pagination cursor") from exc


def apply_cursor(
    stmt: Select,
    created_at_col: ColumnElement,
    id_col: ColumnElement,
    cursor: str | None,
) -> Select:
    if cursor is None:
        return stmt
    cursor_created_at, cursor_id = decode_cursor(cursor)
    return stmt.where(
        or_(
            created_at_col < cursor_created_at,
            and_(created_at_col == cursor_created_at, id_col < cursor_id),
        )
    )
