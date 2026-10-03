"""Chinese display labels; backend enum values remain unchanged."""

LABELS = {
    "gluten-free": "无麸质", "dairy-free": "无乳制品",
    "Imperial (lbs/ft)": "英制（磅 / 英尺）",
    "Metric (kg/cm)": "公制（千克 / 厘米）",
    "sedentary": "久坐", "light": "轻度活动", "moderate": "中等活动",
    "active": "较高活动量", "very_active": "高强度活动",
    "cut": "减脂", "bulk": "增肌", "maintenance": "维持体重", "recomp": "体态重塑（增肌减脂）",
    "dairy": "乳制品", "gluten": "麸质", "nuts": "坚果", "shellfish": "贝类",
    "eggs": "鸡蛋", "soy": "大豆",
    "vegetarian": "素食", "vegan": "纯素", "keto": "生酮饮食", "paleo": "原始饮食",
    "mediterranean": "地中海饮食", "low_carb": "低碳水饮食",
    "bodyweight": "徒手训练", "dumbbells": "哑铃", "barbell": "杠铃",
    "resistance_bands": "弹力带", "pull_up_bar": "引体向上杆", "gym_access": "健身房器械",
    "protein": "蛋白质", "carbohydrate": "碳水化合物", "carbs": "碳水化合物",
    "fat": "脂肪", "high_protein": "高蛋白", "high_carb": "高碳水",
    "high_fat": "高脂肪", "balanced": "均衡", "unknown": "未知",
}


def label(value):
    return LABELS.get(value, value)
