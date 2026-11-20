import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from aiokafka.errors import KafkaError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .broker import EventBroker
from .config import Settings
from .models import MovieEvent, PaymentEvent, UserEvent


def create_app(broker: EventBroker | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.broker = broker if broker is not None else EventBroker(Settings())
        try:
            await app.state.broker.start()
            yield
        finally:
            await app.state.broker.stop()

    app = FastAPI(title='CinemaAbyss Events', lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse({'error': str(error)}, status_code=400)

    @app.get('/api/events/health')
    async def health():
        ready = app.state.broker.ready
        return JSONResponse({'status': ready}, status_code=200 if ready else 503)

    async def publish(event_type: str, payload: BaseModel):
        event = {'id': str(uuid4()), 'type': event_type,
                 'timestamp': datetime.now(timezone.utc).isoformat(),
                 'payload': payload.model_dump(mode='json', exclude_none=True)}
        if not app.state.broker.ready:
            return JSONResponse({'error': 'Kafka unavailable'}, status_code=503)
        try:
            metadata = await asyncio.wait_for(
                app.state.broker.publish(f'{event_type}-events', event), timeout=10)
        except (KafkaError, TimeoutError):
            return JSONResponse({'error': 'Kafka publication failed'}, status_code=503)
        return {'status': 'success', **metadata, 'event': event}

    @app.post('/api/events/movie', status_code=201)
    async def movie_event(payload: MovieEvent):
        return await publish('movie', payload)

    @app.post('/api/events/user', status_code=201)
    async def user_event(payload: UserEvent):
        return await publish('user', payload)

    @app.post('/api/events/payment', status_code=201)
    async def payment_event(payload: PaymentEvent):
        return await publish('payment', payload)

    return app


app = create_app()
