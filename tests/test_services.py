import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from src.microservices.proxy.main import create_app
from src.microservices.proxy.config import Settings
from src.microservices.events.main import create_app as create_events_app


class ProxyTests(unittest.TestCase):
    def test_movie_routing_boundaries(self):
        cases = [(True, 0, 0, 'monolith'), (True, 100, 99, 'movies-service'),
                 (True, 50, 49, 'movies-service'), (True, 50, 50, 'monolith'),
                 (False, 0, 99, 'movies-service')]
        for gradual, percent, bucket, expected in cases:
            with self.subTest(gradual=gradual, percent=percent, bucket=bucket):
                app = create_app(Settings(gradual_migration=gradual, movies_migration_percent=percent))
                with TestClient(app) as client:
                    app.state.client.send = AsyncMock(return_value=httpx.Response(200, content=b'[]'))
                    with patch('src.microservices.proxy.main.random.randrange', return_value=bucket):
                        response = client.get('/api/movies')
                    self.assertEqual(response.headers['x-upstream-service'], expected)

    def test_proxy_preserves_request_and_response(self):
        app = create_app(Settings())
        with TestClient(app) as client:
            transport = httpx.MockTransport(lambda request: httpx.Response(
                201, content=request.content, headers={'x-query': request.url.query.decode()}))
            original = app.state.client
            app.state.client = httpx.AsyncClient(transport=transport)
            response = client.post('/api/users?id=3&id=4', content=b'{"username":"test"}')
            asyncio.run(app.state.client.aclose())
            app.state.client = original
        self.assertEqual((response.status_code, response.content, response.headers['x-query']),
                         (201, b'{"username":"test"}', 'id=3&id=4'))

    def test_unknown_prefix_goes_to_monolith(self):
        app = create_app(Settings(movies_migration_percent=100))
        with TestClient(app) as client:
            app.state.client.send = AsyncMock(return_value=httpx.Response(404))
            response = client.get('/api/movies-extra')
        self.assertEqual(response.headers['x-upstream-service'], 'monolith')

    def test_timeout_returns_gateway_timeout(self):
        app = create_app(Settings())
        with TestClient(app) as client:
            app.state.client.send = AsyncMock(side_effect=httpx.ReadTimeout('timeout'))
            response = client.get('/api/users')
        self.assertEqual(response.status_code, 504)

    def test_events_and_movies_health_have_dedicated_routes(self):
        app = create_app(Settings(movies_migration_percent=0))
        with TestClient(app) as client:
            app.state.client.send = AsyncMock(return_value=httpx.Response(200, content=b'{}'))
            responses = [client.get('/api/events/health'), client.get('/api/movies/health')]
        self.assertEqual([response.headers['x-upstream-service'] for response in responses],
                         ['events-service', 'movies-service'])

    def test_unreachable_upstream_returns_bad_gateway(self):
        app = create_app(Settings())
        with TestClient(app) as client:
            app.state.client.send = AsyncMock(side_effect=httpx.ConnectError('unavailable'))
            response = client.get('/api/users')
        self.assertEqual(response.status_code, 502)

    def test_invalid_migration_percent_is_rejected(self):
        from pydantic import ValidationError
        for percent in (-1, 101):
            with self.subTest(percent=percent), self.assertRaises(ValidationError):
                Settings(movies_migration_percent=percent)


class EventsTests(unittest.TestCase):
    def setUp(self):
        self.broker = AsyncMock()
        self.broker.ready = True
        self.broker.publish.return_value = {'partition': 0, 'offset': 12}
        self.client = TestClient(create_events_app(self.broker))

    def test_event_response_contains_confirmed_metadata(self):
        with self.client as client:
            response = client.post('/api/events/movie', json={
                'movie_id': 1, 'title': 'Inception', 'action': 'viewed'})
        body = response.json()
        self.assertEqual((response.status_code, body['status'], body['partition'],
                          body['offset'], body['event']['type'], body['event']['payload']['movie_id']),
                         (201, 'success', 0, 12, 'movie', 1))

    def test_missing_required_fields_returns_bad_request(self):
        with self.client as client:
            response = client.post('/api/events/payment', json={'payment_id': 1})
        self.assertEqual(response.status_code, 400)

    def test_broker_failure_does_not_return_success(self):
        from aiokafka.errors import KafkaError
        self.broker.publish.side_effect = KafkaError('unavailable')
        with self.client as client:
            response = client.post('/api/events/movie', json={
                'movie_id': 1, 'title': 'Inception', 'action': 'viewed'})
        self.assertEqual(response.status_code, 503)


if __name__ == '__main__':
    unittest.main()
