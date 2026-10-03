import math
import os
from datetime import datetime, timedelta

from pydantic import Field, model_validator

from ..models.base import FitnessModel, as_utc
from ..models.recovery import ReadinessResult, RecoveryInput
from ..models.workout import TrainingLoadResult

LABELS = {"sleep": "睡眠", "hrv": "心率变异性", "rhr": "静息心率",
          "fatigue": "主观疲劳", "soreness": "肌肉酸痛", "load": "近期训练负荷"}
POLICIES = {"HIGH": (1.0, 1.0, 0), "MEDIUM": (.85, .90, -1),
            "LOW": (.65, .80, -2), "VERY_LOW": (.40, .65, -3)}


class ReadinessConfig(FitnessModel):
    sleep: float = Field(default=.30, ge=0, le=1)
    hrv: float = Field(default=.20, ge=0, le=1)
    rhr: float = Field(default=.15, ge=0, le=1)
    fatigue: float = Field(default=.15, ge=0, le=1)
    soreness: float = Field(default=.10, ge=0, le=1)
    load: float = Field(default=.10, ge=0, le=1)
    baseline_sleep_hours: float = Field(default=8, gt=0, le=24)
    load_reference: float = Field(default=3000, gt=0)

    @model_validator(mode="after")
    def check_weights(self) -> "ReadinessConfig":
        if not math.isclose(sum(getattr(self, key) for key in LABELS), 1, abs_tol=1e-9):
            raise ValueError("恢复评分的六项权重之和必须为 1")
        return self

    @classmethod
    def from_env(cls) -> "ReadinessConfig":
        values = {key: os.environ[f"READINESS_{key.upper()}_WEIGHT"] for key in LABELS
                  if f"READINESS_{key.upper()}_WEIGHT" in os.environ}
        for key in ("baseline_sleep_hours", "load_reference"):
            if f"READINESS_{key.upper()}" in os.environ:
                values[key] = os.environ[f"READINESS_{key.upper()}"]
        return cls.model_validate(values)


def readiness_level(score: float) -> str:
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("恢复评分必须在 0 到 100 之间")
    return "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW" if score >= 40 else "VERY_LOW"


def calculate_readiness(
    data: RecoveryInput, *, as_of: datetime, training_load: TrainingLoadResult | None = None,
    config: ReadinessConfig | None = None,
) -> ReadinessResult:
    """确定性工程规则，不做医疗诊断；时间显式传入以便复现。"""
    cfg = config or ReadinessConfig()
    now = as_utc(as_of)
    scores: dict[str, float] = {}
    reasons: list[str] = []
    cap = 100.0
    if data.sleep and timedelta(0) <= now - data.sleep.date <= timedelta(hours=36):
        hours = data.sleep.sleep_duration_hours
        scores["sleep"] = min(hours / cfg.baseline_sleep_hours, 1) ** 2 * 100
        if data.sleep.sleep_score is not None:
            scores["sleep"] = min(scores["sleep"], data.sleep.sleep_score)
        reasons.append(f"睡眠 {hours:g} 小时，计算基准为 {cfg.baseline_sleep_hours:g} 小时。")
        if hours <= 4 or hours > cfg.baseline_sleep_hours * 1.75:
            cap = min(cap, 39)
            reasons.append("睡眠时长明显偏离计算基准，采用保守建议，请核对记录。")
    if data.hrv and timedelta(0) <= now - data.hrv.date <= timedelta(hours=36):
        if data.hrv.hrv_ms is not None and data.hrv.baseline_hrv_ms is not None:
            ratio = data.hrv.hrv_ms / data.hrv.baseline_hrv_ms
            scores["hrv"] = max(0, 100 - max(0, 1 - ratio) * 240)
            reasons.append(f"心率变异性为个人基线的 {ratio * 100:.1f}%。")
    if data.resting_hr is not None and data.baseline_resting_hr is not None:
        delta = data.resting_hr - data.baseline_resting_hr
        scores["rhr"] = max(0, 100 - max(0, delta / data.baseline_resting_hr) * 300)
        reasons.append(f"静息心率较个人基线变化 {delta:+g} 次/分钟。")
    if data.subjective_fatigue is not None:
        scores["fatigue"] = 100 - data.subjective_fatigue * 10
        reasons.append(f"主观疲劳 {data.subjective_fatigue:g}/10。")
        if data.subjective_fatigue >= 8:
            cap = min(cap, 39)
            reasons.append("主观疲劳较高，采用大幅降低训练量的建议。")
    if data.soreness:
        worst = max(data.soreness.values())
        scores["soreness"] = 100 - worst * 10
        reasons.append(f"最高肌肉酸痛评分 {worst:g}/10。")
        if worst >= 8:
            cap = min(cap, 59)
            reasons.append("局部酸痛较高，恢复等级最多为偏低。")
    if training_load is not None:
        if training_load.user_id != data.user_id:
            raise ValueError("训练历史与恢复数据必须属于同一用户")
        if training_load.as_of != now:
            raise ValueError("请使用同一评估时间重新计算训练负荷")
        if training_load.history_complete and training_load.missing_load_sessions == 0:
            scores["load"] = max(0, 100 * (1 - training_load.recent_load / cfg.load_reference))
            reasons.append(f"近七天加权训练负荷为 {training_load.recent_load:.1f}。")
    missing = [key for key in LABELS if key not in scores]
    coverage = sum(getattr(cfg, key) for key in scores)
    score = sum(value * getattr(cfg, key) for key, value in scores.items()) / coverage if coverage else 50.0
    if coverage < .6:
        cap = min(cap, 59)
        reasons.append("有效数据权重不足六成，暂不建议按良好恢复状态训练。")
    if missing:
        reasons.append("缺少或未采用的数据：" + "、".join(LABELS[key] for key in missing) + "；缺失项不视为正常。")
    # 先固定展示精度再分级，避免显示 80 分但等级仍为中等。
    score = round(min(score, cap), 2)
    level = readiness_level(score)
    volume, intensity, rpe = POLICIES[level]
    return ReadinessResult(score=score, level=level, reasons=reasons,
                           recommended_volume_multiplier=volume,
                           recommended_intensity_multiplier=intensity, recommended_rpe_delta=rpe,
                           component_scores=scores, data_coverage=round(coverage, 10), missing_fields=missing)
