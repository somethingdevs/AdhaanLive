import json
from fastapi import APIRouter
from pathlib import Path

router = APIRouter()
FILE = Path("assets/prayer_times.json")

@router.get("/schedule")
def schedule():
    if not FILE.exists():
        return {"error": "schedule not loaded"}
    return json.loads(FILE.read_text())
