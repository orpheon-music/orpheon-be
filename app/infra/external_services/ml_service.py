import asyncio
import logging

import grpc
from grpc import aio

from app.config.settings import get_settings
from app.infra.external_services.proto_gen import echo_pb2, echo_pb2_grpc

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

                if echo_pb2_grpc:
                    self.stub = echo_pb2_grpc.EchoServiceStub(self.channel)

                # Test the connection
                await asyncio.wait_for(self.channel.channel_ready(), timeout=5.0)
                logger.info(f"gRPC client connected to {ml_service_address}")
            except asyncio.TimeoutError:
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

    async def ping(self) -> bool:
        """Ping the ML service to check connectivity"""
        if not self._is_connected() or not echo_pb2:
            logger.debug("gRPC not available, skipping job published notification")
            return False

        try:
            request = echo_pb2.PingRequest(message="ping")

            # Call with timeout
            response = await asyncio.wait_for(self.stub.Ping(request), timeout=3.0)

            if response.success:
                logger.debug("gRPC ping successful")
                return True
            else:
                logger.warning("gRPC ping failed")
                return False

        except asyncio.TimeoutError:
            logger.warning("gRPC timeout pinging ML service")
            return False
        except Exception as e:
            logger.warning(f"Error pinging ML service: {e}")
            return False

    def _is_connected(self) -> bool:
        """Check if gRPC connection is established"""
        return (
            self.channel is not None
            and self.stub is not None
            and self.channel.get_state() != grpc.ChannelConnectivity.SHUTDOWN
        )
