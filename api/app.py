from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import health, status, schedule, control, client_logs

app = FastAPI(
    title="AdhaanLive",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(status.router)
app.include_router(schedule.router)
app.include_router(control.router)
app.include_router(client_logs.router)


app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("frontend/index.html")
