import os
import json
import logging
import time
import signal
import sys
from typing import Dict, Any, Callable
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MQConsumer:
    """
    RabbitMQ Consumer for food notification events.
    
    Responsibilities:
    1. Connect to RabbitMQ and consume messages from queue
    2. Deserialize and validate messages
    3. Pass validated messages to callback handler (notification service)
    4. Handle acknowledgments and errors
    """
    
    def __init__(
        self, 
        callback_handler: Callable[[Dict[str, Any]], bool],
        queue_name: str = None
    ):
        """
        Initialize MQ Consumer
        
        Args:
            callback_handler: Function to call with each message payload
                             Should return True if message processed successfully
            queue_name: Override default queue name from env
        """
        self.callback_handler = callback_handler
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
        self.rabbitmq_queue = queue_name or os.getenv('RABBITMQ_QUEUE', 'food_notifications')
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        
        self.connection = None
        self.channel = None
        self.should_stop = False
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"[MQ_CONSUMER] Initialized for queue: {self.rabbitmq_queue}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"[MQ_CONSUMER] Received signal {signum}, shutting down gracefully...")
        self.should_stop = True
        if self.channel:
            self.channel.stop_consuming()
    
    def _connect(self) -> bool:
        """
        Establish connection to RabbitMQ
        
        Returns:
            bool: True if connected successfully
        """
        try:
            credentials = pika.PlainCredentials(
                self.rabbitmq_user,
                self.rabbitmq_password
            )
            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            logger.info(f"[MQ_CONSUMER] Connecting to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}")
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare queue (idempotent)
            self.channel.queue_declare(
                queue=self.rabbitmq_queue,
                durable=True
            )
            
            # Set QoS - only process one message at a time
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info(f"[MQ_CONSUMER] Connected successfully to queue: {self.rabbitmq_queue}")
            return True
            
        except AMQPConnectionError as e:
            logger.error(f"[MQ_CONSUMER] Failed to connect to RabbitMQ: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"[MQ_CONSUMER] Unexpected error during connection: {str(e)}")
            return False
    
    def _validate_message(self, payload: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate message structure
        
        Args:
            payload: Deserialized message payload
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ['decision', 'food_available', 'club_name']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        if payload['decision'] != 'SEND_NOTIFICATION':
            return False, f"Invalid decision type: {payload['decision']}"
        
        if not payload.get('food_available'):
            return False, "food_available is False, should not be in queue"
        
        return True, ""
    
    def _process_message(
        self, 
        ch, 
        method, 
        properties, 
        body
    ):
        """
        Callback function for processing messages from queue
        
        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body (bytes)
        """
        try:
            # Deserialize message
            message_str = body.decode('utf-8')
            payload = json.loads(message_str)
            
            logger.info(
                f"[MQ_CONSUMER] Received message for club: {payload.get('club_name', 'Unknown')}"
            )
            logger.debug(f"[MQ_CONSUMER] Payload: {json.dumps(payload, indent=2)}")
            
            # Validate message
            is_valid, error_msg = self._validate_message(payload)
            if not is_valid:
                logger.error(f"[MQ_CONSUMER] Invalid message: {error_msg}")
                # Acknowledge to remove from queue (dead letter queue would be better)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Pass to callback handler (notification service)
            logger.info(f"[MQ_CONSUMER] Processing notification for: {payload.get('club_name')}")
            
            success = self.callback_handler(payload)
            
            if success:
                # Acknowledge message - successfully processed
                logger.info(f"[MQ_CONSUMER] ✓ Message processed successfully")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # Reject and requeue for retry
                logger.warning(f"[MQ_CONSUMER] ✗ Message processing failed, requeuing...")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                time.sleep(5)  # Brief delay before retry
                
        except json.JSONDecodeError as e:
            logger.error(f"[MQ_CONSUMER] Failed to decode JSON: {str(e)}")
            ch.basic_ack(delivery_tag=method.delivery_tag)  # Remove invalid message
            
        except Exception as e:
            logger.error(f"[MQ_CONSUMER] Error processing message: {str(e)}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self, auto_reconnect: bool = True):
        """
        Start consuming messages from queue
        
        Args:
            auto_reconnect: Automatically reconnect if connection is lost
        """
        logger.info("[MQ_CONSUMER] Starting consumer...")
        
        while not self.should_stop:
            try:
                # Connect if not connected
                if not self.connection or self.connection.is_closed:
                    if not self._connect():
                        if auto_reconnect:
                            logger.warning("[MQ_CONSUMER] Retrying connection in 5 seconds...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error("[MQ_CONSUMER] Connection failed, exiting")
                            break
                
                # Setup consumer
                self.channel.basic_consume(
                    queue=self.rabbitmq_queue,
                    on_message_callback=self._process_message
                )
                
                logger.info(f"[MQ_CONSUMER] Waiting for messages in queue: {self.rabbitmq_queue}")
                logger.info("[MQ_CONSUMER] Press CTRL+C to exit")
                
                # Start consuming (blocking)
                self.channel.start_consuming()
                
            except AMQPConnectionError as e:
                logger.error(f"[MQ_CONSUMER] Connection lost: {str(e)}")
                if auto_reconnect and not self.should_stop:
                    logger.info("[MQ_CONSUMER] Attempting to reconnect in 5 seconds...")
                    time.sleep(5)
                else:
                    break
                    
            except KeyboardInterrupt:
                logger.info("[MQ_CONSUMER] Keyboard interrupt received")
                self.should_stop = True
                break
                
            except Exception as e:
                logger.error(f"[MQ_CONSUMER] Unexpected error: {str(e)}")
                if auto_reconnect and not self.should_stop:
                    logger.info("[MQ_CONSUMER] Restarting in 5 seconds...")
                    time.sleep(5)
                else:
                    break
        
        self.stop()
    
    def stop(self):
        """Stop consuming and close connections"""
        logger.info("[MQ_CONSUMER] Stopping consumer...")
        
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
                logger.info("[MQ_CONSUMER] Channel closed")
                
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("[MQ_CONSUMER] Connection closed")
        except Exception as e:
            logger.error(f"[MQ_CONSUMER] Error during shutdown: {str(e)}")
        
        logger.info("[MQ_CONSUMER] Shutdown complete")


# Simple test handler for development
def test_handler(payload: Dict[str, Any]) -> bool:
    """Test callback handler that just prints the message"""
    print(f"\n{'='*60}")
    print(f"TEST HANDLER RECEIVED MESSAGE:")
    print(f"Club: {payload.get('club_name')}")
    print(f"Event: {payload.get('event_details', {}).get('title')}")
    print(f"Location: {payload.get('event_details', {}).get('location')}")
    print(f"Time: {payload.get('event_details', {}).get('start_time')}")
    print(f"Confidence: {payload.get('confidence')}")
    print(f"{'='*60}\n")
    return True


# def main():
#     """
#     Main entry point for MQ Consumer service
    
#     In production, import and pass the notification service handler:
#     from services.notifications.__main__ import NotificationService
    
#     notification_service = NotificationService()
#     consumer = MQConsumer(notification_service.send_notification)
#     """
    
#     print("=" * 80)
#     print("MQ CONSUMER SERVICE")
#     print("=" * 80)
#     print()
    
#     # For testing, use test handler
#     # In production, replace with: notification_service.send_notification
#     consumer = MQConsumer(callback_handler=test_handler)
    
#     try:
#         consumer.start_consuming(auto_reconnect=True)
#     except KeyboardInterrupt:
#         logger.info("Shutting down...")
#     finally:
#         consumer.stop()


# if __name__ == "__main__":
#     main()