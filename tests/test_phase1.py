import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from pydantic import ValidationError

from fast_api.app.models.recovery import HRVData, RecoveryInput, SleepData
from fast_api.app.models.workout import ExerciseLog, WorkoutSession, WorkoutSet
from fast_api.app.services.readiness_engine import ReadinessConfig, calculate_readiness, readiness_level
from fast_api.app.services.training_load import calculate_training_load, session_load, training_volume

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def session(**kwargs) -> WorkoutSession:
    return WorkoutSession.model_validate(dict(user_id="甲", date=NOW, session_rpe=5,
                                             duration_minutes=60, **kwargs))


def recovered(**updates) -> RecoveryInput:
    values = dict(user_id="甲", sleep=SleepData(date=NOW, sleep_duration_hours=8),
                  hrv=HRVData(date=NOW, hrv_ms=50, baseline_hrv_ms=50),
                  resting_hr=60, baseline_resting_hr=60, subjective_fatigue=0, soreness={"腿": 0})
    values.update(updates)
    return RecoveryInput.model_validate(values)


class ModelTests(unittest.TestCase):
    def test_sleep_range(self):
        for hours in (-1, 25, float("nan"), float("inf")):
            with self.subTest(hours=hours), self.assertRaises(ValidationError):
                SleepData(sleep_duration_hours=hours)

    def test_sleep_stages(self):
        with self.assertRaises(ValidationError):
            SleepData(sleep_duration_hours=1, deep_sleep_minutes=40, rem_sleep_minutes=30)

    def test_zero_hrv_baseline(self):
        with self.assertRaises(ValidationError):
            HRVData(baseline_hrv_ms=0)

    def test_invalid_rating(self):
        for value in (-1, 11, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RecoveryInput(user_id="甲", soreness={"腿": value})

    def test_empty_user(self):
        with self.assertRaises(ValidationError):
            RecoveryInput(user_id="  ")

    def test_negative_weight(self):
        with self.assertRaises(ValidationError):
            WorkoutSet(weight=-1, reps=10)

    def test_fractional_reps(self):
        with self.assertRaises(ValidationError):
            WorkoutSet(reps=2.5)

    def test_invalid_duration(self):
        with self.assertRaises(ValidationError):
            WorkoutSession(user_id="甲", date=NOW, duration_minutes=0)

    def test_timezone_normalized(self):
        self.assertEqual(SleepData(date=NOW.astimezone(timezone(timedelta(hours=8))), sleep_duration_hours=8).date, NOW)

    def test_naive_is_utc(self):
        self.assertEqual(SleepData(date=NOW.replace(tzinfo=None), sleep_duration_hours=8).date, NOW)

    def test_mutable_defaults(self):
        first, second = session(), session()
        first.exercises.append(ExerciseLog(exercise_name="深蹲"))
        self.assertEqual(second.exercises, [])

    def test_json_roundtrip(self):
        item = recovered()
        self.assertEqual(RecoveryInput.model_validate_json(item.model_dump_json()), item)


class LoadTests(unittest.TestCase):
    def calculate(self, items, complete=True):
        return calculate_training_load(items, user_id="甲", as_of=NOW, history_complete=complete)

    def test_session_load(self):
        self.assertEqual(session_load(session()), 300)

    def test_missing_load(self):
        item = WorkoutSession(user_id="甲", date=NOW)
        self.assertIsNone(session_load(item))
        self.assertEqual(self.calculate([item]).missing_load_sessions, 1)

    def test_volume(self):
        item = session(exercises=[ExerciseLog(exercise_name="深蹲", target_muscle="腿", sets=[
            WorkoutSet(weight=20, reps=10), WorkoutSet(weight=30, reps=5),
            WorkoutSet(weight=100, reps=10, completed=False), WorkoutSet(reps=10)])])
        result = self.calculate([item])
        self.assertEqual(training_volume(item), 350)
        self.assertEqual(result.volume_by_muscle, {"腿": 350})
        self.assertEqual(result.missing_weight_sets, 1)

    def test_incomplete_session(self):
        item = session(completed=False)
        self.assertEqual(session_load(item), 0)
        self.assertEqual(training_volume(item), 0)
        self.assertEqual(self.calculate([item]).session_count, 0)

    def test_seven_day_window(self):
        items = [WorkoutSession(user_id="甲", date=date, session_rpe=7, duration_minutes=10)
                 for date in (NOW, NOW-timedelta(days=6), NOW-timedelta(days=7), NOW+timedelta(seconds=1))]
        result = self.calculate(items)
        self.assertEqual(result.session_count, 2)
        self.assertEqual(result.recent_load, 80)

    def test_other_user(self):
        item = WorkoutSession(user_id="乙", date=NOW, session_rpe=10, duration_minutes=60)
        self.assertEqual(self.calculate([item]).recent_load, 0)

    def test_focus_not_double_counted(self):
        result = self.calculate([session(focus="腿"), session(focus="上肢")])
        self.assertEqual(sum(result.load_by_focus.values()), result.recent_load)

    def test_unknown_history_distinct(self):
        self.assertFalse(self.calculate([], complete=False).history_complete)
        self.assertTrue(self.calculate([]).history_complete)


class ReadinessTests(unittest.TestCase):
    def calculate(self, data=None, **kwargs):
        return calculate_readiness(data or recovered(), as_of=NOW, **kwargs)

    def test_all_good(self):
        result = self.calculate()
        self.assertEqual((result.score, result.level), (100, "HIGH"))
        self.assertEqual(result.recommended_volume_multiplier, 1)

    def test_document_good_example(self):
        data = RecoveryInput(user_id="甲", sleep=SleepData(date=NOW, sleep_duration_hours=8.2),
                             hrv=HRVData(date=NOW, hrv_ms=52.5, baseline_hrv_ms=50), subjective_fatigue=2)
        self.assertEqual(self.calculate(data).level, "HIGH")

    def test_poor_recovery(self):
        data = recovered(sleep=SleepData(date=NOW, sleep_duration_hours=4.5),
                         hrv=HRVData(date=NOW, hrv_ms=37.5, baseline_hrv_ms=50),
                         resting_hr=68, soreness={"腿": 8}, subjective_fatigue=7)
        self.assertIn(self.calculate(data).level, ("LOW", "VERY_LOW"))

    def test_boundaries(self):
        for score, level in [(0,"VERY_LOW"),(39.99,"VERY_LOW"),(40,"LOW"),(59.99,"LOW"),
                             (60,"MEDIUM"),(79.99,"MEDIUM"),(80,"HIGH"),(100,"HIGH")]:
            with self.subTest(score=score):
                self.assertEqual(readiness_level(score), level)

    def test_invalid_scores(self):
        for score in (-1, 101, float("nan")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                readiness_level(score)

    def test_all_missing(self):
        result = self.calculate(RecoveryInput(user_id="甲"))
        self.assertEqual((result.score, result.level, result.data_coverage), (50, "LOW", 0))
        self.assertEqual(len(result.missing_fields), 6)

    def test_sparse_good_data_capped(self):
        result = self.calculate(RecoveryInput(user_id="甲", subjective_fatigue=0))
        self.assertEqual(result.level, "LOW")

    def test_missing_baselines(self):
        result = self.calculate(recovered(hrv=HRVData(date=NOW, hrv_ms=50), baseline_resting_hr=None))
        self.assertIn("hrv", result.missing_fields)
        self.assertIn("rhr", result.missing_fields)

    def test_stale_and_future_sleep(self):
        for date in (NOW-timedelta(hours=37), NOW+timedelta(seconds=1)):
            with self.subTest(date=date):
                result = self.calculate(recovered(sleep=SleepData(date=date, sleep_duration_hours=8)))
                self.assertIn("sleep", result.missing_fields)

    def test_severe_fatigue(self):
        self.assertEqual(self.calculate(recovered(subjective_fatigue=8)).level, "VERY_LOW")

    def test_severe_soreness(self):
        self.assertEqual(self.calculate(recovered(soreness={"腿": 8})).level, "LOW")

    def test_short_and_unusual_sleep(self):
        for hours in (4, 20):
            with self.subTest(hours=hours):
                self.assertEqual(self.calculate(recovered(sleep=SleepData(date=NOW, sleep_duration_hours=hours))).level, "VERY_LOW")

    def test_low_device_score_not_ignored(self):
        result = self.calculate(recovered(sleep=SleepData(date=NOW, sleep_duration_hours=8, sleep_score=20)))
        self.assertEqual(result.component_scores["sleep"], 20)

    def test_monotonic_fatigue(self):
        scores = [self.calculate(recovered(subjective_fatigue=value)).score for value in range(11)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_load_integration(self):
        load = calculate_training_load([session()], user_id="甲", as_of=NOW, history_complete=True)
        result = self.calculate(training_load=load)
        self.assertEqual(result.component_scores["load"], 90)
        self.assertEqual(result.score, 99)

    def test_unknown_load_excluded(self):
        load = calculate_training_load([], user_id="甲", as_of=NOW)
        self.assertIn("load", self.calculate(training_load=load).missing_fields)

    def test_incomplete_load_excluded(self):
        load = calculate_training_load([WorkoutSession(user_id="甲", date=NOW)], user_id="甲", as_of=NOW, history_complete=True)
        self.assertIn("load", self.calculate(training_load=load).missing_fields)

    def test_wrong_user_rejected(self):
        load = calculate_training_load([], user_id="乙", as_of=NOW, history_complete=True)
        with self.assertRaises(ValueError):
            self.calculate(training_load=load)

    def test_repeatable(self):
        self.assertEqual(self.calculate().model_dump(), self.calculate().model_dump())

    def test_stale_load_rejected(self):
        load = calculate_training_load([], user_id="甲", as_of=NOW-timedelta(days=1), history_complete=True)
        with self.assertRaises(ValueError):
            self.calculate(training_load=load)

    def test_config_validation(self):
        with self.assertRaises(ValidationError):
            ReadinessConfig(sleep=.5)
        with self.assertRaises(ValidationError):
            ReadinessConfig(load_reference=0)

    def test_environment_weights(self):
        values = {f"READINESS_{key.upper()}_WEIGHT": str(value) for key,value in
                  dict(sleep=.4,hrv=.1,rhr=.15,fatigue=.15,soreness=.1,load=.1).items()}
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(ReadinessConfig.from_env().sleep, .4)

    def test_four_policies(self):
        for fatigue, expected in [(0,(1,1,0)),(3,(.85,.9,-1)),(5,(.65,.8,-2)),(9,(.4,.65,-3))]:
            config = ReadinessConfig(sleep=0,hrv=0,rhr=0,fatigue=1,soreness=0,load=0)
            result = self.calculate(RecoveryInput(user_id="甲", subjective_fatigue=fatigue), config=config)
            self.assertEqual((result.recommended_volume_multiplier, result.recommended_intensity_multiplier,
                              result.recommended_rpe_delta), expected)


if __name__ == "__main__":
    unittest.main()
