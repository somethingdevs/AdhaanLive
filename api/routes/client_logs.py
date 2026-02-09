from fastapi import APIRouter, Request
import logging

router = APIRouter(prefix="/client-log")

@router.post("")
async def client_log(request: Request):
    payload = await request.json()
    client_logger = logging.getLogger("adhaanlive.client")
    client_logger.info(payload)
    return {"ok": True}
