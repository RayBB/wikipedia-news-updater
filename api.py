"""
uv run uvicorn api:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import json
from change_collector import start_page_creation

app = FastAPI()

DATA_DIR = Path("data")


@app.get("/")
def get_index():
    return FileResponse("index.html")

# http://127.0.0.1:8000/json/California_Senate_Bill_79

@app.get("/json/{filename}")
def get_json(filename: str):
    # Prevent path traversal like ../../../etc/passwd
    safe_name = Path(filename).name
    file_path = DATA_DIR / f"{safe_name}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="JSON file not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON format")

@app.get("/json_create/{filename}")
def json_create(filename: str, limit: int = 10):
    start_page_creation(filename, limit)
    return None
