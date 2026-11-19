import asyncio
import json
import logging
from contextlib import suppress

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from .config import Settings

logger = logging.getLogger('uvicorn.error')
TOPICS = ('movie-events', 'user-events', 'payment-events')
STARTUP_ATTEMPTS = 30
RETRY_DELAY = 2


class EventBroker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.producer = None
        self.consumer = None
        self.task = None
        self.ready = False

    async def start(self) -> None:
        for attempt in range(STARTUP_ATTEMPTS):
            try:
                await self.connect()
                self.ready = True
                self.task = asyncio.create_task(self.consume())
                return
            except (KafkaError, OSError):
                await self.stop()
                if attempt == STARTUP_ATTEMPTS - 1:
                    raise
                logger.warning('Kafka not ready; retry %s/%s', attempt + 1, STARTUP_ATTEMPTS)
                await asyncio.sleep(RETRY_DELAY)

    async def connect(self) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.settings.kafka_brokers.split(','), acks='all',
            value_serializer=lambda event: json.dumps(event).encode(),
        )
        await self.producer.start()
        self.consumer = AIOKafkaConsumer(
            *TOPICS, bootstrap_servers=self.settings.kafka_brokers.split(','),
            group_id=self.settings.kafka_consumer_group,
            auto_offset_reset='earliest', enable_auto_commit=False,
        )
        await self.consumer.start()

    async def stop(self) -> None:
        self.ready = False
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def publish(self, topic: str, event: dict) -> dict:
        metadata = await self.producer.send_and_wait(topic, event)
        return {'partition': metadata.partition, 'offset': metadata.offset}

    async def consume(self) -> None:
        try:
            async for message in self.consumer:
                logger.info('Processed event: topic=%s partition=%s offset=%s event=%s',
                            message.topic, message.partition, message.offset,
                            message.value.decode())
                await self.consumer.commit()
        except Exception:
            self.ready = False
            logger.exception('Event consumer stopped')
