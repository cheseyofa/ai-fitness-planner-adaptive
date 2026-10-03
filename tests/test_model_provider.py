import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fast_api.app.model_provider import create_chat_model, create_embeddings, structured_chat
from fast_api.app.runtime import require_openai_key


class ProviderTests(unittest.TestCase):
    def test_deepseek_routing(self):
        with patch.dict(os.environ, {"CHAT_PROVIDER":"deepseek", "DEEPSEEK_API_KEY":"test-only"}, clear=True):
            model = create_chat_model()
            self.assertEqual(model.model_name, "deepseek-flash")
            self.assertEqual(model.openai_api_base, "https://api.deepseek.com")
            self.assertEqual(create_chat_model(advanced=True).model_name, "deepseek-v4-pro")
            require_openai_key()

    def test_missing_chat_key(self):
        with patch.dict(os.environ, {"CHAT_PROVIDER":"deepseek", "OPENAI_API_KEY":"other-provider"}, clear=True):
            with self.assertRaises(HTTPException): require_openai_key()

    def test_no_embedding_credential_leak(self):
        with patch.dict(os.environ, {"CHAT_PROVIDER":"deepseek", "DEEPSEEK_API_KEY":"test-only"}, clear=True):
            with self.assertRaises(HTTPException): create_embeddings()

    def test_openai_compatibility(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only"}, clear=True):
            self.assertEqual(create_chat_model().model_name,"gpt-4o-mini")
            self.assertEqual(create_embeddings().model,"text-embedding-3-small")

    def test_explicit_embedding_endpoint(self):
        with patch.dict(os.environ, {"EMBEDDING_API_KEY":"test-only", "EMBEDDING_BASE_URL":"https://example.invalid/v1", "EMBEDDING_MODEL":"test-model"}, clear=True):
            model=create_embeddings()
            self.assertEqual(model.openai_api_base,"https://example.invalid/v1")
            self.assertEqual(model.model,"test-model")

    def test_tool_calling_format(self):
        from unittest.mock import Mock
        model=Mock(); schema=Mock()
        structured_chat(model,schema)
        model.with_structured_output.assert_called_once_with(schema,method="function_calling")
