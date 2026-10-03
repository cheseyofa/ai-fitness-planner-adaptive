"""Local startup checks; never sends Agent, embedding, or database requests."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def check_server(name, args, path):
    log_path = ROOT / "docs" / f"{name}_startup.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, *args], stdout=log, stderr=log)
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited: see {log_path}")
                try:
                    with urllib.request.urlopen(path, timeout=1) as response:
                        body = response.read()
                        if name == "fastapi":
                            schema = json.loads(body)
                            assert len(schema["paths"]) > 0
                            print(f"API paths: {len(schema['paths'])}")
                        print(f"{name} HTTP {response.status}: PASS")
                        return
                except (OSError, ValueError):
                    time.sleep(0.5)
            raise TimeoutError(name)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    (ROOT / "docs").mkdir(exist_ok=True)
    for module in ["fastapi", "uvicorn", "langgraph", "langchain", "langchain_openai",
                   "openai", "faiss", "pymongo", "langsmith", "streamlit", "requests", "httpx", "dotenv"]:
        importlib.import_module(module)
        print(f"{module} import: PASS", flush=True)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from fast_api.app.main import app
    print(f"FastAPI application import: PASS ({len(app.routes)} routes)")
    check_server("fastapi", ["-m", "uvicorn", "fast_api.app.main:app", "--host", "127.0.0.1", "--port", "18000"],
                 "http://127.0.0.1:18000/openapi.json")
    home = next((ROOT / "streamlit" / "streamlit").glob("*home.py"))
    check_server("streamlit", ["-m", "streamlit", "run", str(home), "--server.address=127.0.0.1",
                              "--server.port=18501", "--server.headless=true", "--browser.gatherUsageStats=false"],
                 "http://127.0.0.1:18501/_stcore/health")
    sys.path.insert(0, str(home.parent))
    from streamlit.testing.v1 import AppTest
    page = AppTest.from_file(str(home)).run(timeout=30)
    assert not page.exception, [str(e) for e in page.exception]
    print("Streamlit home page execution: PASS")
