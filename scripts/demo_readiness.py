"""第一阶段离线中文演示；示例数据不写入数据库。"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fast_api.app.models.recovery import HRVData, RecoveryInput, SleepData
from fast_api.app.services.readiness_engine import calculate_readiness


def main() -> None:
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    now = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
    cases = {
        "恢复良好": RecoveryInput(user_id="演示", sleep=SleepData(date=now, sleep_duration_hours=8.2),
                                hrv=HRVData(date=now, hrv_ms=52.5, baseline_hrv_ms=50), subjective_fatigue=2),
        "疲劳较高": RecoveryInput(user_id="演示", sleep=SleepData(date=now, sleep_duration_hours=4.5),
                                hrv=HRVData(date=now, hrv_ms=37.5, baseline_hrv_ms=50),
                                resting_hr=68, baseline_resting_hr=60, subjective_fatigue=8, soreness={"腿": 8}),
        "数据缺失": RecoveryInput(user_id="演示"),
    }
    labels = {"HIGH": "良好", "MEDIUM": "中等", "LOW": "偏低", "VERY_LOW": "很低"}
    print("离线示例数据，仅演示计算规则，尚未接入网页或实际训练计划。")
    for name, data in cases.items():
        result = calculate_readiness(data, as_of=now)
        print(f"\n{name}：{result.score:.2f} 分，恢复状态{labels[result.level]}")
        print(f"建议训练量为原计划的 {result.recommended_volume_multiplier:.0%}，"
              f"强度为 {result.recommended_intensity_multiplier:.0%}，"
              f"主观用力程度调整 {result.recommended_rpe_delta:g} 分。")
        for reason in result.reasons:
            print(f"  · {reason}")


if __name__ == "__main__":
    main()
