import csv
from fastapi import APIRouter, Query
from pathlib import Path

router = APIRouter()
LOG_FILE = Path("assets/adhaan_log.csv")

@router.get("/events")
def events(limit: int = Query(100, le=500)):
    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open() as f:
        rows = list(csv.DictReader(f))

    return rows[-limit:]
