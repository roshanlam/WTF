"""
LLM Agent Service for Free Food Event Detection

This service:
1. Consumes events from Redis Stream
2. Uses Ollama LLM to analyze event context for free food mentions
3. Publishes positive detections to notification queue
"""

import logging
import sys
import json
from typing import Optional
import requests

from services.config import REDIS_URL, MQ_STREAM
from services.mq import Consumer, MessageQueue
from models import FreeFoodEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url
        self.model = model
        self.endpoint = f"{base_url}/api/generate"
    
    def check_free_food(self, event_context: str) -> tuple[bool, str]:
        """
        Analyze event context to determine if it mentions free food.
        
        Returns:
            tuple: (has_free_food: bool, reasoning: str)
        """
        prompt = f"""Analyze the following event description for a UMass Amherst university event.

Event Description:
{event_context}

Task: Determine if this event explicitly mentions FREE FOOD or FREE MEALS for attendees.

Rules:
- Look for keywords like: "free food", "free pizza", "free lunch", "free dinner", "free snacks", "refreshments provided", "food will be provided", "complimentary food"
- Be strict: only return YES if food is clearly stated to be free
- Ignore paid meals, suggested donations, or food available for purchase
- Return ONLY "YES" or "NO" followed by a brief reason

Format your response as:
ANSWER: [YES/NO]
REASON: [brief explanation]"""

        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,  # Low temperature for consistent responses
                },
                timeout=30,
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Parse the response
            has_free_food = "ANSWER: YES" in response_text.upper()
            
            # Extract reasoning
            reasoning = "No reasoning provided"
            if "REASON:" in response_text:
                reasoning = response_text.split("REASON:")[-1].strip()
            
            return has_free_food, reasoning
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            # Fallback to simple keyword matching
            return self._fallback_check(event_context)
    
    def _fallback_check(self, event_context: str) -> tuple[bool, str]:
        """Fallback keyword-based check if Ollama is unavailable"""
        keywords = [
            "free food", "free pizza", "free lunch", "free dinner",
            "free breakfast", "free snacks", "free refreshments",
            "complimentary food", "food provided", "refreshments provided"
        ]
        
        context_lower = event_context.lower()
        for keyword in keywords:
            if keyword in context_lower:
                return True, f"Fallback detection: Found keyword '{keyword}'"
        
        return False, "Fallback detection: No free food keywords found"


class FreeFoodDetector:
    """Main service for detecting free food events"""
    
    def __init__(self):
        self.llm_client = OllamaClient()
        self.consumer = Consumer(
            redis_url=REDIS_URL,
            stream_name=MQ_STREAM,
            consumer_group="llm-agent",
            consumer_name="free-food-detector",
        )
        self.notification_queue = MessageQueue(
            redis_url=REDIS_URL,
            stream_name="events.notifications",  # Separate stream for notifications
        )
    
    def process_event(self, event: FreeFoodEvent):
        """Process a single event to detect free food"""
        logger.info(f"Processing event: {event.event_id} - {event.title}")
        
        # Construct context from event data
        event_context = self._build_context(event)
        
        # Use LLM to check for free food
        has_free_food, reasoning = self.llm_client.check_free_food(event_context)
        
        logger.info(f"Event {event.event_id}: Free food = {has_free_food}")
        logger.info(f"Reasoning: {reasoning}")
        
        if has_free_food:
            # Publish to notification queue
            try:
                # Enrich event with detection metadata
                event.metadata = event.metadata or {}
                event.metadata["llm_detection"] = {
                    "has_free_food": True,
                    "reasoning": reasoning,
                    "detector": "llm-agent",
                }
                
                self.notification_queue.publish(event)
                logger.info(f"✓ Published notification for event {event.event_id}")
            except Exception as e:
                logger.error(f"Failed to publish notification: {e}")
        else:
            logger.info(f"✗ No free food detected for event {event.event_id} - Noop")
    
    def _build_context(self, event: FreeFoodEvent) -> str:
        """Build a comprehensive context string from event data"""
        context_parts = [
            f"Event Title: {event.title}",
            f"Description: {event.description}",
            f"Location: {event.location}",
            f"Start Time: {event.start_time}",
            f"End Time: {event.end_time}",
        ]
        
        if event.organizer:
            context_parts.append(f"Organizer: {event.organizer}")
        
        if event.tags:
            context_parts.append(f"Tags: {', '.join(event.tags)}")
        
        if event.metadata:
            context_parts.append(f"Additional Info: {json.dumps(event.metadata)}")
        
        return "\n".join(context_parts)
    
    def run(self):
        """Start the consumer and process events"""
        logger.info("Starting Free Food Detector LLM Agent")
        logger.info(f"Consuming from: {MQ_STREAM}")
        logger.info(f"Publishing to: events.notifications")
        
        try:
            self.consumer.consume(handler=self.process_event)
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        finally:
            self.consumer.close()
            self.notification_queue.close()


def main():
    """Entry point for the LLM agent service"""
    try:
        detector = FreeFoodDetector()
        detector.run()
    except Exception as e:
        logger.error(f"Fatal error in LLM agent: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()