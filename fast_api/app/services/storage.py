"""Bounded Mongo operations run outside the event loop."""
import asyncio
import os
import hashlib
import json
from typing import Any
from ..runtime import connect_mongo


class MongoStore:
    async def find(self, collection: str, query: dict, *, limit: int = 200,
                   sort_key: str = "date") -> list[dict[str, Any]]:
        def run():
            with connect_mongo() as client:
                return list(client[os.getenv("MONGO_DB_NAME", "usda_nutrition")][collection]
                            .find(query, {"_id": 0}).sort(sort_key, -1).limit(limit))
        return await asyncio.to_thread(run)

    async def save(self, collection: str, query: dict, data: dict) -> None:
        identifier=hashlib.sha256(json.dumps(query,sort_keys=True,default=str).encode()).hexdigest()
        def run():
            with connect_mongo() as client:
                client[os.getenv("MONGO_DB_NAME", "usda_nutrition")][collection].replace_one(
                    {"_id":identifier}, {**data,"_id":identifier}, upsert=True)
        await asyncio.to_thread(run)


store = MongoStore()
