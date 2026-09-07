"""
Retrieval-Augmented Generation for Yuri AI. Retrieves the real, closest
catalogue matches for the user's question via pgvector cosine similarity,
then asks Claude to answer using ONLY that retrieved context. If nothing
relevant is retrieved, Claude is instructed to say so rather than guess.
"""

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Product, ProductEmbedding
from app.services.embeddings import embed_text

SYSTEM_PROMPT = """You are Yuri AI, the skincare coach inside the YuriWoori app.

Rules:
- Answer ONLY using the CONTEXT block below. It contains real product data retrieved for this question.
- If the context doesn't contain enough to answer, say you don't have that information in the catalogue — never invent a product, ingredient, or claim.
- Keep answers short (2-4 sentences), warm, and practical.
- Do not give medical or dermatological diagnoses. For persistent skin concerns, suggest seeing a dermatologist.
"""


def retrieve_context(db: Session, query: str, top_k: int = 4) -> list[Product]:
    query_vector = embed_text(query)

    results = (
        db.execute(
            select(Product, ProductEmbedding)
            .join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
            .order_by(ProductEmbedding.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        .all()
    )
    return [row[0] for row in results]


def ask_yuri(db: Session, conversation_history: list[dict], question: str) -> tuple[str, list[str]]:
    matched_products = retrieve_context(db, question)

    context_lines = []
    for p in matched_products:
        context_lines.append(
            f"- {p.name} | ₹{p.price} | category: {p.category} | routine step: {p.routine_step} | "
            f"addresses: {', '.join(p.concern_tags or []) or 'general use'} | {p.description or ''}"
        )
    context_block = "\n".join(context_lines) if context_lines else "No closely matching products found."

    client = Anthropic(api_key=settings.anthropic_api_key)

    messages = conversation_history + [
        {"role": "user", "content": f"CONTEXT:\n{context_block}\n\nQUESTION: {question}"}
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    reply_text = "".join(block.text for block in response.content if block.type == "text")
    cited_ids = [str(p.id) for p in matched_products]

    return reply_text, cited_ids