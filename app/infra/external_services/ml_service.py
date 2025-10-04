import asyncio
import logging

import grpc
from grpc import aio

from app.config.settings import get_settings
from gen import ml_pb2, ml_pb2_grpc

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.channel: aio.Channel | None = None
        self.stub: any | None = None  # type: ignore
        self._connection_lock = asyncio.Lock()

    async def connect(self):
        """Establish connection to the ML service"""
        settings = get_settings()

        async with self._connection_lock:
            if (
                self.channel
                and not self.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN
            ):
                return

            try:
                ml_service_address = (
                    f"{settings.ML_SERVICE_HOST}:{settings.ML_SERVICE_PORT}"
                )
                self.channel = aio.insecure_channel(ml_service_address)

                if ml_pb2_grpc:
                    self.stub = ml_pb2_grpc.MLServiceStub(self.channel)

                # Test the connection
                await asyncio.wait_for(self.channel.channel_ready(), timeout=5.0)
                logger.info(f"gRPC client connected to {ml_service_address}")
            except TimeoutError:
                logger.warning(
                    "gRPC connection timeout - continuing without gRPC notifications"
                )
                await self.disconnect()
            except Exception as e:
                logger.warning(f"Failed to connect to gRPC server: {e}")
                await self.disconnect()

    async def disconnect(self):
        """Close connection to the ML service"""
        async with self._connection_lock:
            if self.channel:
                await self.channel.close()
                self.channel = None
                self.stub = None
                logger.info("gRPC client disconnected")

    async def process(
        self,
        audio_processing_id: str,
        voice_file_url: str,
        instrument_file_url: str,
        reference_file_url: str,
        is_denoise: bool,
        is_autotune: bool,
    ) -> bool:
        if not self._is_connected() or not ml_pb2:
            logger.debug("gRPC not available, skipping job published notification")
            return False

        try:
            request = ml_pb2.ProcessRequest(
                audio_processing_id=audio_processing_id,
                voice_file_url=voice_file_url,
                instrument_file_url=instrument_file_url,
                reference_file_url=reference_file_url,
                is_denoise=is_denoise,
                is_autotune=is_autotune,
            )

            # Call with timeout
            response = await asyncio.wait_for(self.stub.Process(request), timeout=3.0)

            logger.info(f"gRPC process response: {response}")
            return True
        except TimeoutError:
            logger.warning("gRPC timeout processing audio")
            return False

    def _is_connected(self) -> bool:
        """Check if gRPC connection is established"""
        return (
            self.channel is not None
            and self.stub is not None
            and self.channel.get_state() != grpc.ChannelConnectivity.SHUTDOWN
        )
