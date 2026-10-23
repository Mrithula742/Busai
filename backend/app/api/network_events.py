from fastapi import APIRouter, HTTPException, Request
from ..schemas.network_event import NetworkEvent

router = APIRouter()


@router.post('/api/network-events', status_code=201, response_model=NetworkEvent)
async def create_event(event: NetworkEvent, request: Request):
    try:
        return request.app.state.events.create(event)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/api/network-events')
async def list_events(request: Request, include_cleared: bool = False):
    request.app.state.events.expire()
    return request.app.state.events.list(include_cleared)


@router.post('/api/network-events/{event_id}/clear', response_model=NetworkEvent)
async def clear_event(event_id: str, request: Request):
    try:
        demo_events = getattr(request.app.state, 'ai_events', None)
        if demo_events is not None and any(event.event_id == event_id for event in demo_events.list(True)):
            return demo_events.clear(event_id)
        return request.app.state.events.clear(event_id)
    except KeyError as exc:
        raise HTTPException(404, 'Unknown event_id') from exc
