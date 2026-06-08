from fastapi import APIRouter

from app.schemas.webhooks import WebhookAck, WebhookIn

router = APIRouter(prefix="/webhooks/n8n", tags=["webhooks"])


@router.post("/smartjobs", response_model=WebhookAck)
def smartjobs_webhook(payload: WebhookIn):
    return WebhookAck(ok=True, message="smartjobs webhook received")


@router.post("/linkedin", response_model=WebhookAck)
def linkedin_webhook(payload: WebhookIn):
    return WebhookAck(ok=True, message="linkedin webhook received")