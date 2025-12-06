import os
import sys
import time
import uuid
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import FreeFoodEvent
from services.mq import MessageQueue
from services.decision_gateway.__main__ import DecisionGateway

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UnifiedPipeline:
    """
    Unified pipeline that processes tweets through the complete workflow:
    CSV → Decision Gateway → LLM → Redis MQ → Email Notifications
    """
    
    def __init__(
        self,
        model_path: str = "@cf/meta/llama-3.1-8b-instruct-fast",
        rate_limit_delay: float = 0.5
    ):
        """
        Initialize the unified pipeline.
        
        Args:
            model_path: LLM model to use
            rate_limit_delay: Delay between processing tweets (seconds)
        """
        self.model_path = model_path
        self.rate_limit_delay = rate_limit_delay
        
        # Initialize components
        logger.info("Initializing pipeline components...")
        self.decision_gateway = DecisionGateway(model_path=model_path)
        self.message_queue = MessageQueue()
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "food_detected": 0,
            "published_to_mq": 0,
            "errors": 0,
            "total_latency": 0.0
        }
        
        logger.info("✓ Pipeline initialized successfully")
    
    def _create_event_from_payload(
        self, 
        payload: dict, 
        original_data: dict
    ) -> FreeFoodEvent:
        """
        Create a FreeFoodEvent from decision gateway payload.
        
        Args:
            payload: Decision payload from gateway
            original_data: Original tweet data
            
        Returns:
            FreeFoodEvent instance
        """
        event_details = payload.get("event_details", {})
        processing_meta = payload.get("processing_metadata", {})
        
        # Parse start_time if present
        start_time = None
        start_time_str = event_details.get("start_time")
        if start_time_str and start_time_str != "Time TBD":
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse start_time '{start_time_str}': {e}")
        
        return FreeFoodEvent(
            event_id=str(uuid.uuid4()),
            title=event_details.get("title", "Free Food Event"),
            description=payload.get("original_tweet", ""),
            location=event_details.get("location"),
            start_time=start_time,
            source=f"social_media_{payload.get('club_name', 'unknown')}",
            llm_confidence=payload.get("confidence"),
            reason=processing_meta.get("llm_reason", ""),
            published_at=datetime.now(),
            metadata={
                "club_name": payload.get("club_name", "Unknown"),
                "raw_post": payload.get("original_tweet", ""),
                "ground_truth": processing_meta.get("ground_truth"),
                "processing_latency": processing_meta.get("llm_latency_seconds"),
                "llm_model": processing_meta.get("llm_model"),
            }
        )
    
    def process_single_tweet(self, row_data: dict) -> dict:
        """
        Process a single tweet through the entire pipeline.
        
        Args:
            row_data: Dictionary with 'club_name', 'tweet', 'food_label'
            
        Returns:
            Processing result dictionary
        """
        club_name = row_data.get("club_name", "Unknown")
        tweet = row_data.get("tweet", "")
        
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Processing tweet from: {club_name}")
        logger.info(f"Tweet preview: {tweet[:100]}...")
        logger.info(f"{'=' * 70}")
        
        start_time = time.time()
        
        try:
            # Step 1: Decision Gateway (includes LLM processing)
            logger.info("[STEP 1/3] Running Decision Gateway + LLM...")
            decision = self.decision_gateway.process_tweet(row_data)
            
            if decision["decision"] == "ERROR":
                logger.error(f"❌ Decision gateway error: {decision.get('error')}")
                self.stats["errors"] += 1
                return {
                    "success": False,
                    "club_name": club_name,
                    "error": decision.get("error"),
                    "stage": "decision_gateway"
                }
            
            # Step 2: Publish to Message Queue (if food detected)
            if decision["decision"] == "SEND_NOTIFICATION":
                logger.info("[STEP 2/3] Food detected! Creating event...")
                
                payload = decision["payload"]
                event = self._create_event_from_payload(payload, row_data)
                
                logger.info(f"  Event: {event.title}")
                logger.info(f"  Location: {event.location}")
                logger.info(f"  Confidence: {event.llm_confidence:.2f}")
                logger.info(f"  Reason: {event.reason}")
                
                # Publish to Redis MQ
                logger.info("[STEP 3/3] Publishing to message queue...")
                message_id = self.message_queue.publish(event)
                
                logger.info(f"✅ Published to MQ! Message ID: {message_id}")
                logger.info(f"   Consumer services will now process this event")
                logger.info(f"   → MQ Consumer: Will log event details")
                logger.info(f"   → Notification Service: Will send emails")
                
                self.stats["food_detected"] += 1
                self.stats["published_to_mq"] += 1
                
                result = {
                    "success": True,
                    "club_name": club_name,
                    "food_detected": True,
                    "event_id": event.event_id,
                    "message_id": message_id,
                    "confidence": event.llm_confidence,
                    "event_title": event.title
                }
            else:
                logger.info("[STEP 2/3] No food detected")
                logger.info(f"  Reason: {decision.get('payload', {}).get('processing_metadata', {}).get('llm_reason', 'N/A')}")
                logger.info("❌ No action taken - skipping MQ publish")
                
                result = {
                    "success": True,
                    "club_name": club_name,
                    "food_detected": False,
                    "reason": decision.get("payload", {}).get("processing_metadata", {}).get("llm_reason", "")
                }
            
            elapsed = time.time() - start_time
            self.stats["total_processed"] += 1
            self.stats["total_latency"] += elapsed
            
            logger.info(f"⏱️  Total processing time: {elapsed:.2f}s")
            
            return result
            
        except Exception as e:
            logger.exception(f"❌ Pipeline error for {club_name}: {str(e)}")
            self.stats["errors"] += 1
            return {
                "success": False,
                "club_name": club_name,
                "error": str(e),
                "stage": "pipeline_exception"
            }
    
    def process_csv(self, csv_file: str) -> dict:
        """
        Process all tweets from a CSV file through the pipeline.
        
        Args:
            csv_file: Path to CSV file with columns: club_name, tweet, food_label
            
        Returns:
            Summary statistics and results
        """
        logger.info("\n" + "=" * 70)
        logger.info("UNIFIED PIPELINE - STARTING BATCH PROCESSING")
        logger.info("=" * 70)
        logger.info(f"CSV File: {csv_file}")
        logger.info(f"Model: {self.model_path}")
        logger.info("=" * 70 + "\n")
        
        try:
            # Load CSV
            df = pd.read_csv(csv_file)
            logger.info(f"📄 Loaded {len(df)} tweets from CSV\n")
            
            results = []
            
            for idx, row in df.iterrows():
                row_data = row.to_dict()
                logger.info(f"[{idx + 1}/{len(df)}] Processing...")
                
                result = self.process_single_tweet(row_data)
                results.append(result)
                
                # Rate limiting
                if idx < len(df) - 1:  # Don't sleep after last item
                    time.sleep(self.rate_limit_delay)
            
            # Print summary
            self._print_summary(results)
            
            return {
                "stats": self.stats,
                "results": results
            }
            
        except FileNotFoundError:
            logger.error(f"❌ CSV file not found: {csv_file}")
            return {"error": "file_not_found", "stats": self.stats}
        except Exception as e:
            logger.exception(f"❌ Batch processing error: {str(e)}")
            return {"error": str(e), "stats": self.stats}
    
    def _print_summary(self, results: list):
        """Print processing summary."""
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total Processed:       {self.stats['total_processed']}")
        logger.info(f"Food Detected:         {self.stats['food_detected']}")
        logger.info(f"Published to MQ:       {self.stats['published_to_mq']}")
        logger.info(f"Errors:                {self.stats['errors']}")
        
        if self.stats['total_processed'] > 0:
            avg_latency = self.stats['total_latency'] / self.stats['total_processed']
            logger.info(f"Average Latency:       {avg_latency:.2f}s")
            
            success_rate = ((self.stats['total_processed'] - self.stats['errors']) / 
                          self.stats['total_processed'] * 100)
            logger.info(f"Success Rate:          {success_rate:.1f}%")
            
            if self.stats['food_detected'] > 0:
                detection_rate = (self.stats['food_detected'] / 
                                self.stats['total_processed'] * 100)
                logger.info(f"Food Detection Rate:   {detection_rate:.1f}%")
        
        logger.info("=" * 70)
        
        # Show published events
        published = [r for r in results if r.get("food_detected")]
        if published:
            logger.info("\n📧 Events Published (will be sent via email):")
            for i, event in enumerate(published, 1):
                logger.info(f"  {i}. {event.get('event_title')} - {event.get('club_name')}")
                logger.info(f"     Event ID: {event.get('event_id')}")
                logger.info(f"     Confidence: {event.get('confidence', 0):.2f}")
        
        logger.info("\n💡 Next Steps:")
        logger.info("   1. Ensure MQ Consumer is running: python -m services.mq_consumer")
        logger.info("   2. Ensure Notification Service is running: python -m services.notification_service")
        logger.info("   3. Check logs for email delivery confirmation")
        logger.info("=" * 70 + "\n")
    
    def close(self):
        """Clean up resources."""
        logger.info("Closing pipeline connections...")
        self.message_queue.close()
        logger.info("✓ Pipeline closed")


def main():
    """Main entry point for the unified pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Unified Pipeline - Process tweets through complete workflow"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="/Users/akarshgupta/Desktop/Fall 25/532/final_project/WTF/sample_events.csv",
        help="Path to CSV file with tweets"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="@cf/meta/llama-3.1-8b-instruct-fast",
        help="LLM model path"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between processing tweets (seconds)"
    )
    
    args = parser.parse_args()
    
    # Create and run pipeline
    pipeline = UnifiedPipeline(
        model_path=args.model,
        rate_limit_delay=args.delay
    )
    
    try:
        results = pipeline.process_csv(args.csv)
        
        # Exit with error code if there were errors
        if results.get("stats", {}).get("errors", 0) > 0:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  Pipeline interrupted by user")
        sys.exit(130)
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()