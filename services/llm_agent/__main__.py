import os
import sys
import time
import json
import uuid
import logging
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Add parent directory to path to import models and services
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models import FreeFoodEvent
from services.mq import MessageQueue

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_agent_json_mode(row_data, model_path):
    """
    Send tweet to Cloudflare AI using JSON mode with schema.
    Args:
        row_data: dict with keys 'club_name', 'tweet', 'food_label'
        model_path: the model path to use (e.g., '@cf/meta/llama-3.1-8b-instruct-fast')
    Returns:
        ok (bool), latency (float), result (dict), ground_truth (int)
    """
    API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
    API_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        start = time.time()

        tweet = row_data.get("tweet", "")
        ground_truth = int(row_data.get("food_label", 0))

        api_url = f"https://api.cloudflare.com/client/v4/accounts/{API_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct-fast"

        # Payload with JSON mode and schema following FreeFoodEvent structure
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": """You are a precise assistant that detects food availability at events from social media posts.

CRITICAL RULES:
1. Extract event information ONLY if the post explicitly mentions food, snacks, drinks, meals, refreshments, or similar items being served/provided.
2. Look for keywords like: food, snacks, pizza, bagels, cookies, lunch, dinner, breakfast, drinks, refreshments, BBQ, burritos, pasta, sandwiches, etc.
3. If no food is mentioned, set food_available to false and DO NOT include location, start_time, or title fields.
4. Extract a clear event title from the post (e.g., "Career Fair at Goodell Lawn" or "Cultural Showcase")
5. Parse dates and times carefully (format as ISO 8601: YYYY-MM-DDTHH:MM:SS)
6. Provide a confidence score (0.0-1.0) based on how explicit the food mention is
7. Include a brief reason explaining your decision

Examples:
- "Free pizza at the career fair today at 2pm in Student Union!"
  → food_available: true, title: "Career Fair", location: "Student Union", start_time: "2025-12-03T14:00:00"
- "Join us for a meeting this Thursday"
  → food_available: false (no other fields)
- "Come to our workshop, snacks provided! Integrative Learning Center on 08/23/2025"
  → food_available: true, title: "Workshop", location: "Integrative Learning Center", start_time: "2025-08-23T00:00:00" """,
                },
                {
                    "role": "user",
                    "content": f"Club: {row_data.get('club_name', 'Unknown')}\nTweet: {tweet}",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "type": "object",
                    "properties": {
                        "food_available": {
                            "type": "boolean",
                            "description": "True only if food/drinks/snacks are explicitly mentioned as being provided",
                        },
                        "title": {
                            "type": "string",
                            "description": "The event title/name. Only include if food_available is true.",
                        },
                        "location": {
                            "type": "string",
                            "description": "The location where the event will take place. Only include if food_available is true.",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "The date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS). Only include if food_available is true.",
                        },
                        "llm_confidence": {
                            "type": "number",
                            "description": "Confidence score between 0.0 and 1.0 indicating certainty of food availability detection",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why food was or wasn't detected",
                        },
                    },
                    "required": ["food_available", "llm_confidence", "reason"],
                },
            },
        }

        response = requests.post(api_url, headers=HEADERS, json=payload, timeout=45)

        latency = time.time() - start

        if response.status_code == 200:
            try:
                json_result = response.json()
                # Parse the JSON response from the model
                response_text = json_result.get("result", {}).get("response")
                if response_text:
                    # The response should already be a JSON object
                    if isinstance(response_text, dict):
                        result = response_text
                    else:
                        result = json.loads(response_text)

                    # Add club_name to the result
                    result["club_name"] = row_data.get("club_name", "Unknown")

                    return True, latency, result, ground_truth
                else:
                    return False, latency, None, ground_truth
            except Exception as e:
                print(f"[ERROR] JSON parse error: {str(e)}")
                print(f"[ERROR] Raw response: {json_result}")
                return False, latency, None, ground_truth
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            print(f"[ERROR] {error_msg}")
            return False, latency, None, ground_truth

    except Exception as e:
        latency = time.time() - start
        print(f"[ERROR] Exception: {str(e)}")
        return False, latency, None, 0


def process_and_publish_event(
    row_data: dict, model_path: str, mq: MessageQueue
) -> tuple[bool, float]:
    """
    Process a single event with the LLM and publish to message queue if food is detected.

    Args:
        row_data: dict with keys 'club_name', 'tweet', 'food_label'
        model_path: the model path to use
        mq: MessageQueue instance for publishing

    Returns:
        tuple of (success: bool, latency: float)
    """
    ok, latency, result, ground_truth = run_agent_json_mode(row_data, model_path)

    if not ok or result is None:
        logger.warning(
            f"LLM processing failed for event from {row_data.get('club_name', 'Unknown')}"
        )
        return False, latency

    food_available = result.get("food_available", False)

    if food_available:
        try:
            # Create FreeFoodEvent from LLM result
            event = FreeFoodEvent(
                event_id=str(uuid.uuid4()),
                title=result.get("title", "Free Food Event"),
                description=row_data.get("tweet", ""),
                location=result.get("location"),
                start_time=datetime.fromisoformat(result["start_time"])
                if result.get("start_time")
                else None,
                source=f"social_media_{row_data.get('club_name', 'unknown')}",
                llm_confidence=result.get("llm_confidence"),
                reason=result.get("reason"),
                published_at=datetime.now(),
                metadata={
                    "club_name": row_data.get("club_name", "Unknown"),
                    "raw_post": row_data.get("tweet", ""),
                    "ground_truth": ground_truth,
                    "processing_latency": latency,
                },
            )

            # Publish to message queue
            message_id = mq.publish(event)
            logger.info(
                f"✅ Published event {event.event_id} to queue (msg_id: {message_id})"
            )
            logger.info(f"   Title: {event.title}")
            logger.info(f"   Location: {event.location}")
            logger.info(f"   Confidence: {event.llm_confidence:.2f}")
            logger.info(f"   Reason: {event.reason}")

            return True, latency
        except Exception as e:
            logger.error(f"Failed to publish event: {str(e)}")
            return False, latency
    else:
        logger.info(
            f"❌ No food detected in post from {row_data.get('club_name', 'Unknown')}"
        )
        logger.info(f"   Reason: {result.get('reason', 'N/A')}")
        return True, latency


def run_llm_agent_service(
    csv_file: str, model_path: str = "@cf/meta/llama-3.1-8b-instruct-fast"
):
    """
    Main service function that processes events from a CSV file and publishes to message queue.

    Args:
        csv_file: Path to CSV file with columns: club_name, tweet, food_label
        model_path: LLM model to use
    """
    logger.info("Starting LLM Agent Service")
    logger.info(f"Reading events from: {csv_file}")
    logger.info(f"Using model: {model_path}")

    # Initialize message queue
    mq = MessageQueue()

    try:
        # Read CSV file
        df = pd.read_csv(csv_file)
        logger.info(f"Loaded {len(df)} events from CSV")

        total_processed = 0
        # total_published = 0 commented out as it was not being used,
        # remove it if it is not used in the future.
        total_latency = 0.0

        for idx, row in df.iterrows():
            row_data = row.to_dict()
            logger.info(
                f"\n[{idx + 1}/{len(df)}] Processing event from {row_data.get('club_name', 'Unknown')}"
            )

            success, latency = process_and_publish_event(row_data, model_path, mq)
            total_processed += 1
            total_latency += latency

            if success:
                # Check if event was actually published (food_available was true)
                # This is a bit indirect, but we can infer from the logs
                pass

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        # Print summary
        avg_latency = total_latency / total_processed if total_processed > 0 else 0
        logger.info(f"\n{'=' * 60}")
        logger.info("LLM Agent Service Summary")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total events processed: {total_processed}")
        logger.info(f"Average latency: {avg_latency:.2f}s")
        logger.info(f"{'=' * 60}")

    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file}")
    except Exception as e:
        logger.error(f"Error in LLM agent service: {str(e)}")
    finally:
        mq.close()
        logger.info("Message queue connection closed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="LLM Agent Service - Process events and publish to message queue"
    )
    parser.add_argument(
        "--csv", type=str, help="Path to CSV file with events", required=False
    )
    parser.add_argument(
        "--model",
        type=str,
        default="@cf/meta/llama-3.1-8b-instruct-fast",
        help="Model path",
    )

    args = parser.parse_args()

    if args.csv:
        run_llm_agent_service(args.csv, args.model)
    else:
        print("No CSV file provided. Use --csv to specify input file.")
        print("Example: python -m services.llm_agent --csv data/events.csv")
