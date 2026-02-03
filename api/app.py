from fastapi import FastAPI
from api.routes import health, status, schedule, control
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AdhaanLive",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(status.router)
app.include_router(schedule.router)
app.include_router(control.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:63342",  # JetBrains preview
        "http://localhost:8000",   # same-origin (safe)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

