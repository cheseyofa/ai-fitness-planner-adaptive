"""Shared local/container connection settings and runtime prerequisites."""
import os
from fastapi import HTTPException
from pymongo import MongoClient


def connect_mongo():
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "mongodb_ai_fitness_planner"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=os.getenv("MONGO_USER") or None,
        password=os.getenv("MONGO_PASSWORD") or None,
        authSource="admin", serverSelectionTimeoutMS=3000,
    )
    try:
        client.admin.command("ping")
        return client
    except Exception:
        client.close()
        raise


def require_openai_key():
    # Compatibility name retained for existing API callers.
    from .model_provider import chat_key
    if not chat_key():
        raise HTTPException(status_code=503, detail="智能服务尚未配置，请先在本地配置模型服务密钥。")


CHINESE_OUTPUT = """
所有面向用户的文字值必须使用简体中文，包括食物名称、餐名、星期、训练动作、
器械、训练方式、建议和总结。JSON 字段名保持指定结构不变，数值不得篡改。
食物及动作名称忠实翻译，品牌专有名词可保留，不得编造食物来源或营养数据。
份量采用克、毫升等中国用户熟悉的公制单位。
"""
