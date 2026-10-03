"""Offline UI checks: no database writes or real AI requests."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "streamlit" / "streamlit"
sys.path.insert(0, str(UI))
from streamlit.testing.v1 import AppTest
from utils.api_client import FitnessAPI


def assert_ok(page):
    assert not page.exception, [e.message for e in page.exception]


with patch.object(FitnessAPI, "test_connection", return_value={"success": True}), \
     patch.object(FitnessAPI, "runtime_status", return_value={"database_ready":True,"food_count":5000,"model_key_configured":True,"embedding_key_configured":False,"vector_index_ready":False,"ready":False}), \
     patch.object(FitnessAPI, "get_profile", return_value={}), \
     patch.object(FitnessAPI, "check_database_availability", return_value={}):
    home = AppTest.from_file(str(UI / "🏠_home.py"), default_timeout=20).run()
    assert_ok(home)
    assert home.title[0].value == "🏋️‍♂️ 智能健身助手"
    profile = AppTest.from_file(str(UI / "pages/1_👤_Profile_Setup.py"), default_timeout=20).run()
    assert_ok(profile)
    assert profile.selectbox[0].options == ["英制（磅 / 英尺）", "公制（千克 / 厘米）"]
    profile.selectbox[0].select("Metric (kg/cm)")
    with patch.object(FitnessAPI, "create_profile", return_value={}) as save:
        profile.button[0].click().run()
        assert_ok(profile)
        payload = save.call_args.args[0]
        assert payload["activity_level"] == "moderate"
        assert payload["fitness_goal"] == "maintenance"
        assert payload["equipment_available"] == ["bodyweight", "dumbbells"]
    plan = AppTest.from_file(str(UI / "pages/2_📊_Complete_Plan.py"), default_timeout=20).run()
    assert_ok(plan)
    assert "请先创建个人资料" in plan.warning[0].value
    plan.session_state["current_profile"] = {"workout_frequency": 3}
    plan.run()
    assert_ok(plan)
    assert any(b.label == "🚀 生成完整计划" for b in plan.button)
    search = AppTest.from_file(str(UI / "pages/3_🔍_Food_Search.py"), default_timeout=20).run()
    for mode in ["🔍 基础搜索", "🧠 按需求搜索", "🎯 高级筛选"]:
        search.radio[0].set_value(mode).run()
        assert_ok(search)
    home.switch_page("pages/1_👤_Profile_Setup.py").run()
    assert_ok(home)
    assert home.header[0].value == "👤 个人资料设置"
print("PASS: Chinese home/navigation/profile/plan/search modes; backend enum values preserved.")
