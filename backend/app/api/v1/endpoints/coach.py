import logging
import uuid
from anthropic import APIError, APIStatusError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.db.models import CoachConversation, CoachMessage, CoachRole
from app.schemas import CoachMessageRequest, CoachMessageResponse
from app.services.coach import ask_yuri

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/message", response_model=CoachMessageResponse)
def send_message(payload: CoachMessageRequest, db: Session = Depends(get_db)):
    if payload.conversation_id:
        conversation = db.get(CoachConversation, payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = CoachConversation()
        db.add(conversation)
        db.flush()

    history = [
        {"role": m.role.value, "content": m.content}
        for m in sorted(conversation.messages, key=lambda m: m.created_at)
    ]

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI assistant is not configured: ANTHROPIC_API_KEY is missing in .env")

    try:
        reply_text, cited_ids = ask_yuri(db, history, payload.message)
    except APIStatusError as exc:
        logger.error("Anthropic API error (%s): %s", exc.status_code, exc.message)
        if "credit balance is too low" in exc.message:
            raise HTTPException(
                status_code=503,
                detail="AI assistant is unavailable: the Anthropic account has run out of API credits. "
                "Add credits at console.anthropic.com and try again.",
            )
        raise HTTPException(status_code=502, detail=f"The AI assistant service failed to respond: {exc.message}")
    except APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        raise HTTPException(status_code=502, detail="The AI assistant service failed to respond. Please try again.")

    db.add(CoachMessage(conversation_id=conversation.id, role=CoachRole.user, content=payload.message))
    db.add(
        CoachMessage(
            conversation_id=conversation.id,
            role=CoachRole.assistant,
            content=reply_text,
            cited_product_ids=cited_ids,
        )
    )
    db.commit()

    return CoachMessageResponse(
        conversation_id=conversation.id,
        reply=reply_text,
        cited_product_ids=cited_ids,
    )