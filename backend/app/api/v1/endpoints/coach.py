import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import CoachConversation, CoachMessage, CoachRole
from app.schemas import CoachMessageRequest, CoachMessageResponse
from app.services.coach import ask_yuri

router = APIRouter()


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

    reply_text, cited_ids = ask_yuri(db, history, payload.message)

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