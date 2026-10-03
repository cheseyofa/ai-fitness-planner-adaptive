import os
from pathlib import Path
from fastapi import APIRouter
from ..runtime import connect_mongo
from ..model_provider import chat_key, chat_provider, embedding_key

health = APIRouter()


@health.get("/health")
def readiness():
    count = 0
    database = False
    try:
        with connect_mongo() as client:
            count = client[os.getenv("MONGO_DB_NAME", "usda_nutrition")].branded_foods_sample.count_documents({})
            database = True
    except Exception:
        pass
    key_configured = bool(chat_key())
    embeddings_configured = bool(embedding_key())
    index_exists = all((Path("nutrition_faiss_index_sample") / filename).is_file()
                       for filename in ("index.faiss", "index.pkl"))
    return {"database_ready": database, "food_count": count,
            "chat_provider": chat_provider(), "embedding_key_configured": embeddings_configured,
            "model_key_configured": key_configured, "vector_index_ready": index_exists,
            "ready": database and count > 0 and key_configured and embeddings_configured and index_exists}
