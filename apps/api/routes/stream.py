from fastapi import APIRouter, Depends, Query, Request

from apps.api.auth import decode_token
from apps.api.settings import get_settings
from services.event_bus import sse_response

router = APIRouter(tags=["Stream"])


@router.get("/stream/events")
async def stream_events(request: Request, access_token: str | None = Query(default=None)):
    settings = get_settings()
    if settings.require_auth:
        header = request.headers.get("authorization") or ""
        token = None
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
        elif access_token:
            token = access_token
        if not token:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        decode_token(token)
    return await sse_response(request)
