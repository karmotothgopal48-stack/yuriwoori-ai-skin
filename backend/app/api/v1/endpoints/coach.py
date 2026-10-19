import logging
import uuid
from anthropic import APIError, APIStatusError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import optional_user
from app.db.session import get_db
from app.db.models import CoachConversation, CoachMessage, CoachRole, User
from app.schemas import CoachMessageRequest, CoachMessageResponse
from app.services.coach import ask_yuri
from app.services.live_catalogue import LiveCatalogueUnavailable, get_catalogue

router = APIRouter()
logger = logging.getLogger(__name__)

# Shown to users; the technical cause is only logged server-side.
UNAVAILABLE = "Yuri AI is not available right now. Please try again later."


@router.post("/message", response_model=CoachMessageResponse)
def send_message(payload: CoachMessageRequest, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if payload.conversation_id:
        conversation = db.get(CoachConversation, payload.conversation_id)
        # another user's conversation is reported as missing, so its history can't be continued or probed
        if not conversation or (conversation.user_id and conversation.user_id != (user.id if user else None)):
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = CoachConversation(user_id=user.id if user else None)
        db.add(conversation)
        db.flush()

    history = [
        {"role": m.role.value, "content": m.content}
        for m in sorted(conversation.messages, key=lambda m: m.created_at)
    ]

    if not settings.anthropic_api_key:
        logger.error("AI assistant is not configured: ANTHROPIC_API_KEY is missing in .env")
        raise HTTPException(status_code=503, detail=UNAVAILABLE)

    try:
        reply_text, cited_ids = ask_yuri(db, history, payload.message, get_catalogue())
    except LiveCatalogueUnavailable as exc:
        logger.error("Coach unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    except APIStatusError as exc:
        logger.error("Anthropic API error (%s): %s", exc.status_code, exc.message)
        raise HTTPException(status_code=503 if "credit balance is too low" in exc.message else 502, detail=UNAVAILABLE)
    except APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        raise HTTPException(status_code=502, detail=UNAVAILABLE)

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