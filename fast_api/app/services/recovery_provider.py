from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from ..models.recovery import RecoveryInput
from .storage import MongoStore, store


class RecoveryDataProvider(ABC):
    @abstractmethod
    async def get_recovery(self, user_id: str, as_of: datetime) -> RecoveryInput: ...

    async def get_sleep(self, user_id: str, as_of: datetime):
        return (await self.get_recovery(user_id, as_of)).sleep

    async def get_hrv(self, user_id: str, as_of: datetime):
        return (await self.get_recovery(user_id, as_of)).hrv

    async def get_resting_hr(self, user_id: str, as_of: datetime):
        return (await self.get_recovery(user_id, as_of)).resting_hr


class ManualRecoveryProvider(RecoveryDataProvider):
    def __init__(self, repository: MongoStore = store):
        self.repository = repository

    async def get_recovery(self, user_id: str, as_of: datetime) -> RecoveryInput:
        rows = await self.repository.find("recovery_records", {"user_id": user_id,
            "date": {"$lte": as_of, "$gt": as_of-timedelta(hours=36)}}, limit=1)
        return RecoveryInput.model_validate(rows[0]["input"]) if rows else RecoveryInput(user_id=user_id)


class MockRecoveryProvider(RecoveryDataProvider):
    """Explicit fixture injection only; never selected by production defaults."""
    def __init__(self, data: RecoveryInput):
        self.data = data

    async def get_recovery(self, user_id: str, as_of: datetime) -> RecoveryInput:
        if user_id != self.data.user_id:
            raise ValueError("恢复数据不属于当前用户")
        return self.data.model_copy(deep=True)
