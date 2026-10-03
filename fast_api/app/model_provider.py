"""Chat and embedding credentials are deliberately isolated."""
import os

from fastapi import HTTPException
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


def chat_provider() -> str:
    provider = os.getenv("CHAT_PROVIDER", "openai").strip().lower()
    if provider not in ("openai", "deepseek"):
        raise ValueError("不支持的聊天模型服务配置")
    return provider


def chat_key() -> str:
    name = "DEEPSEEK_API_KEY" if chat_provider() == "deepseek" else "OPENAI_API_KEY"
    return os.getenv(name, "").strip()


def create_chat_model(*, temperature: float = .3, advanced: bool = False) -> ChatOpenAI:
    deepseek = chat_provider() == "deepseek"
    model = os.getenv("CHAT_ADVANCED_MODEL" if advanced else "CHAT_MODEL") or (
        ("deepseek-v4-pro" if advanced else "deepseek-flash") if deepseek
        else ("o3-mini" if advanced else "gpt-4o-mini"))
    options = dict(model=model, api_key=chat_key() or "not-configured",
                   base_url=os.getenv("CHAT_BASE_URL") or (
                       "https://api.deepseek.com" if deepseek else "https://api.openai.com/v1"),
                   timeout=180, max_retries=1)
    if not model.startswith("o3"):
        options["temperature"] = temperature
    if deepseek:
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(**options)


def structured_chat(model: ChatOpenAI, schema, *, include_raw: bool = False):
    # Explicit tool calling avoids OpenAI-only json_schema response formatting.
    if include_raw:
        return model.with_structured_output(schema, method="function_calling", include_raw=True)
    return model.with_structured_output(schema, method="function_calling")


def embedding_key() -> str:
    return (os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def create_embeddings() -> OpenAIEmbeddings:
    if not embedding_key():
        raise HTTPException(status_code=503, detail="食品语义检索尚未配置嵌入服务；聊天模型密钥不能替代嵌入服务密钥。")
    return OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small",
                            api_key=embedding_key(),
                            base_url=os.getenv("EMBEDDING_BASE_URL") or "https://api.openai.com/v1",
                            request_timeout=60, max_retries=1)
