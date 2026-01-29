from fastapi import FastAPI
from api.routes import health, status, events, schedule, control

app = FastAPI(
    title="AdhaanLive",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(status.router)
app.include_router(events.router)
app.include_router(schedule.router)
app.include_router(control.router)
