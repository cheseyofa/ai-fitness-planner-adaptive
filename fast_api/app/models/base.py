from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class FitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


def as_utc(value: datetime) -> datetime:
    """无时区的历史时间按 UTC 解释；新调用方应传入带时区时间。"""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
