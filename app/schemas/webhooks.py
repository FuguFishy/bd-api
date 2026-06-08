from typing import Any, Optional

from pydantic import BaseModel


class WebhookIn(BaseModel):
    source: Optional[str] = None
    event: Optional[str] = None
    payload: dict[str, Any] = {}


class WebhookAck(BaseModel):
    ok: bool
    message: str