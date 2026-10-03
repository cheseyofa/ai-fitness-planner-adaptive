"""Offline regression tests; fake embeddings must never enter production indexes."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from fast_api.app.main import app
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.api import agents, nutrition_search as search
from app import chinese
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document


class TestEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(i), 1.0, 0.0] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return [0.0, 1.0, 0.0]


class RuntimeTests(unittest.TestCase):
    def test_translation_keeps_nutrition_and_source(self):
        foods = [{"fdc_id": 99, "description": "OATS", "nutrition_per_100g": {"calories": 389}}]
        with patch.object(chinese, "_translate", return_value={0: {"description": "燕麦", "food_category": "谷物", "matched_content": ""}}):
            result = chinese.localize_food_results(foods)
        self.assertEqual(result[0]["description"], "燕麦")
        self.assertEqual(result[0]["nutrition_per_100g"], foods[0]["nutrition_per_100g"])
        self.assertEqual(result[0]["original_description"], "OATS")
        self.assertEqual(foods[0]["description"], "OATS")

    def test_failed_embedding_does_not_save_partial_index(self):
        client = MagicMock()
        collection = client.__getitem__.return_value.__getitem__.return_value
        collection.count_documents.return_value = 2
        collection.find.return_value = [{"fdcId": 1, "description": "test"}, {"fdcId": 2, "description": "test"}]
        with tempfile.TemporaryDirectory(prefix="fitness-failed-index-") as folder, \
             patch.object(search, "get_mongo_client", return_value=client), \
             patch.object(search, "get_embeddings_model", return_value=TestEmbeddings()), \
             patch.object(search, "require_openai_key"), \
             patch.object(search.FAISS, "from_documents", side_effect=RuntimeError("test unavailable")):
            with self.assertRaises(HTTPException):
                asyncio.run(search._create_vector_index("test-only", str(Path(folder) / "index"), batch_size=1))
            self.assertFalse((Path(folder) / "index/index.faiss").exists())

    def test_database_failure_is_not_success(self):
        with patch.object(agents, "get_mongo_client", side_effect=RuntimeError("offline")):
            result = TestClient(app).post("/v1/agents/profile/", json={"user_id": "test-only"})
        self.assertEqual(result.status_code, 503)

    def test_missing_profile_stays_404(self):
        client = MagicMock()
        client.__getitem__.return_value.__getitem__.return_value.find_one.return_value = None
        with patch.object(agents, "get_mongo_client", return_value=client):
            result = TestClient(app).get("/v1/agents/profile/missing-test-only")
        self.assertEqual(result.status_code, 404)

    def test_missing_key_blocks_ai_without_network(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "DEEPSEEK_API_KEY": ""}):
            result = TestClient(app).post("/v1/langgraph/generate-fitness-plan/", json={"user_id": "test-only"})
        self.assertEqual(result.status_code, 503)

    def test_all_batches_are_preserved(self):
        client = MagicMock()
        collection = client.__getitem__.return_value.__getitem__.return_value
        collection.count_documents.return_value = 5
        collection.find.return_value = [{"fdcId": i, "description": f"food {i}"} for i in range(5)]
        with tempfile.TemporaryDirectory(prefix="fitness-index-test-") as folder, \
             patch.object(search, "get_mongo_client", return_value=client), \
             patch.object(search, "get_embeddings_model", return_value=TestEmbeddings()), \
             patch.object(search, "require_openai_key"):
            result = asyncio.run(search._create_vector_index("test-only", str(Path(folder) / "index"), batch_size=2))
        self.assertEqual(result["index_size"], 5)
        self.assertEqual(result["total_documents_processed"], 5)

    def test_lower_distance_is_better(self):
        store = MagicMock()
        store.similarity_search_with_score.return_value = [
            (Document(page_content="food", metadata={"fdc_id": 1}), 0.1),
            (Document(page_content="food", metadata={"fdc_id": 2}), 1.2),
        ]
        with patch.object(search, "get_vector_store", return_value=store), \
             patch.object(search, "require_openai_key"):
            result = asyncio.run(search.search_nutrition_semantic(search.NutritionQuery(query="food", similarity_threshold=0.7, localize=False)))
        self.assertEqual([food["fdc_id"] for food in result.results], [1])
        self.assertAlmostEqual(result.results[0]["similarity_score"], 0.95)


if __name__ == "__main__":
    unittest.main()
