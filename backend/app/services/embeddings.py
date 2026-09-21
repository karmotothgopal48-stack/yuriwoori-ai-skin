_model = None


def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy import (torch): load on first use

        _model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, runs fully locally
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()