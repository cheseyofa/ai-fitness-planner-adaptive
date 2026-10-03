import unittest
from datetime import datetime,timezone
from fast_api.app.models.recovery import RecoveryInput,SleepData,HRVData
from fast_api.app.services.readiness_engine import calculate_readiness

NOW=datetime(2026,10,3,0,tzinfo=timezone.utc)
CASES=[(hours,fatigue,expected) for hours,fatigue,expected in [
    (8,0,'HIGH'),(8,1,'HIGH'),(8,2,'HIGH'),(8,3,'HIGH'),(8,4,'HIGH'),(8,5,'HIGH'),
    (8,6,'HIGH'),(8,7,'HIGH'),(8,8,'VERY_LOW'),(8,9,'VERY_LOW'),(8,10,'VERY_LOW'),
    (6,0,'MEDIUM'),(6,7,'MEDIUM'),(5,7,'LOW'),(4.5,7,'LOW'),(3,4,'VERY_LOW'),
    (4,0,'VERY_LOW'),(4,3,'VERY_LOW'),(4,6,'VERY_LOW'),(4,9,'VERY_LOW'),
    (20,0,'VERY_LOW'),(20,2,'VERY_LOW'),(20,5,'VERY_LOW'),(20,7,'VERY_LOW')]]


def evaluate_case(hours,fatigue):
    return calculate_readiness(RecoveryInput(user_id='fixture',sleep=SleepData(date=NOW,sleep_duration_hours=hours),
        hrv=HRVData(date=NOW,hrv_ms=50,baseline_hrv_ms=50),subjective_fatigue=fatigue),as_of=NOW)


class FixedCases(unittest.TestCase):
    def test_readiness_fixed_cases(self):
        for hours,fatigue,expected in CASES:
            with self.subTest(hours=hours,fatigue=fatigue):self.assertEqual(evaluate_case(hours,fatigue).level,expected)
