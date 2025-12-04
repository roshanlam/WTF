import os
import json
import time
import logging
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Import your LLM agent function
from services.llm_agent.__main__ import run_agent_json_mode as llm_agent_main

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DecisionGateway:
    """
    Gateway service that processes LLM agent responses and decides next actions.
    
    Responsibilities:
    1. Send tweet to LLM agent for food detection
    2. Process and validate LLM response
    3. Return structured decision data for downstream services
    """
    
    def __init__(self, model_path: str = '@cf/meta/llama-3.1-8b-instruct-fast'):
        self.model_path = model_path
        
    def _validate_llm_result(self, llm_result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the LLM result structure and content
        
        Args:
            llm_result: Result dictionary from LLM agent
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not llm_result:
            return False, "LLM result is None or empty"
        
        # Check required fields
        required_fields = ['food_available', 'llm_confidence', 'reason']
        for field in required_fields:
            if field not in llm_result:
                return False, f"Missing required field: {field}"
        
        # Validate food_available is boolean
        if not isinstance(llm_result['food_available'], bool):
            return False, "food_available must be boolean"
        
        # Validate confidence score
        confidence = llm_result.get('llm_confidence')
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            return False, "llm_confidence must be between 0.0 and 1.0"
        
        # If food is available, check for event details
        if llm_result['food_available']:
            event_fields = ['title', 'location', 'start_time']
            missing_fields = [f for f in event_fields if f not in llm_result or not llm_result[f]]
            if missing_fields:
                logger.warning(f"Food detected but missing fields: {missing_fields}")
                # Don't fail validation, but log the warning
        
        return True, ""
    
    def _create_decision_payload(
        self, 
        llm_result: Dict[str, Any], 
        original_data: Dict[str, Any],
        latency: float,
        ground_truth: int
    ) -> Dict[str, Any]:
        """
        Create standardized decision payload for downstream services
        
        Args:
            llm_result: Result from LLM agent
            original_data: Original tweet data
            latency: LLM processing time
            ground_truth: Ground truth label
            
        Returns:
            Structured decision payload
        """
        food_available = llm_result.get('food_available', False)
        
        payload = {
            'decision': 'SEND_NOTIFICATION' if food_available else 'NO_ACTION',
            'food_available': food_available,
            'confidence': llm_result.get('llm_confidence', 0.0),
            'club_name': llm_result.get('club_name', original_data.get('club_name', 'Unknown')),
            'original_tweet': original_data.get('tweet', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'processing_metadata': {
                'llm_latency_seconds': round(latency, 3),
                'llm_model': self.model_path,
                'ground_truth': ground_truth,
                'llm_reason': llm_result.get('reason', '')
            }
        }
        
        # Add event details if food is available
        if food_available:
            payload['event_details'] = {
                'title': llm_result.get('title', 'Food Event'),
                'location': llm_result.get('location', 'Location TBD'),
                'start_time': llm_result.get('start_time', 'Time TBD')
            }
        
        return payload
    
    def process_tweet(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main decision gateway logic for processing a single tweet
        
        Args:
            row_data: Dictionary with keys 'club_name', 'tweet', 'food_label'
            
        Returns:
            Dictionary containing:
                - decision: 'SEND_NOTIFICATION', 'NO_ACTION', or 'ERROR'
                - status: processing status
                - payload: data for downstream services (if decision is SEND_NOTIFICATION)
                - error: error message (if status is error)
        """
        tweet = row_data.get('tweet', '')
        club_name = row_data.get('club_name', 'Unknown')
        
        logger.info(f"[GATEWAY] Processing tweet from: {club_name}")
        logger.debug(f"[GATEWAY] Tweet content: {tweet[:100]}...")
        
        # Step 1: Send to LLM Agent
        try:
            success, latency, llm_result, ground_truth = llm_agent_main(
                row_data, 
                self.model_path
            )
            
            # Handle LLM agent failure
            if not success or llm_result is None:
                logger.error(f"[GATEWAY] LLM agent failed for {club_name}")
                return {
                    'decision': 'ERROR',
                    'status': 'llm_agent_failed',
                    'club_name': club_name,
                    'error': 'LLM agent returned no result',
                    'latency': latency
                }
            
            logger.info(f"[GATEWAY] LLM response received in {latency:.3f}s")
            
            # Step 2: Validate LLM result
            is_valid, error_msg = self._validate_llm_result(llm_result)
            if not is_valid:
                logger.error(f"[GATEWAY] Invalid LLM result: {error_msg}")
                return {
                    'decision': 'ERROR',
                    'status': 'invalid_llm_result',
                    'club_name': club_name,
                    'error': error_msg,
                    'llm_result': llm_result
                }
            
            # Step 3: Make decision based on food availability
            food_available = llm_result.get('food_available', False)
            confidence = llm_result.get('llm_confidence', 0.0)
            
            logger.info(
                f"[GATEWAY] Decision for {club_name}: "
                f"food={food_available}, confidence={confidence:.2f}"
            )
            
            # Step 4: Create decision payload
            decision_payload = self._create_decision_payload(
                llm_result,
                row_data,
                latency,
                ground_truth
            )
            
            # Step 5: Return decision
            if food_available:
                logger.info(
                    f"[GATEWAY] ✓ SEND_NOTIFICATION - {club_name} - "
                    f"{decision_payload.get('event_details', {}).get('title', 'N/A')}"
                )
                return {
                    'decision': 'SEND_NOTIFICATION',
                    'status': 'success',
                    'payload': decision_payload
                }
            else:
                logger.info(f"[GATEWAY] ✗ NO_ACTION - {club_name} - No food detected")
                return {
                    'decision': 'NO_ACTION',
                    'status': 'success',
                    'payload': decision_payload
                }
            
        except Exception as e:
            logger.error(f"[GATEWAY] Exception processing tweet from {club_name}: {str(e)}")
            return {
                'decision': 'ERROR',
                'status': 'exception',
                'club_name': club_name,
                'error': str(e)
            }
    
    def process_batch(self, tweets: list) -> Dict[str, Any]:
        """
        Process a batch of tweets and return aggregated decisions
        
        Args:
            tweets: List of row_data dictionaries
            
        Returns:
            Summary statistics and list of all decisions
        """
        logger.info(f"[GATEWAY] Starting batch processing: {len(tweets)} tweets")
        
        results = {
            'total_processed': len(tweets),
            'notifications_to_send': 0,
            'no_action': 0,
            'errors': 0,
            'decisions': []
        }
        
        for idx, tweet_data in enumerate(tweets, 1):
            logger.info(f"[GATEWAY] Processing tweet {idx}/{len(tweets)}")
            
            decision = self.process_tweet(tweet_data)
            results['decisions'].append(decision)
            
            # Update counters
            if decision['decision'] == 'SEND_NOTIFICATION':
                results['notifications_to_send'] += 1
            elif decision['decision'] == 'NO_ACTION':
                results['no_action'] += 1
            else:
                results['errors'] += 1
        
        logger.info(
            f"[GATEWAY] Batch complete: "
            f"{results['notifications_to_send']} to notify, "
            f"{results['no_action']} no action, "
            f"{results['errors']} errors"
        )
        
        return results
    
    def get_notifications_from_batch(self, batch_results: Dict[str, Any]) -> list:
        """
        Extract only the notification payloads from batch results
        
        Args:
            batch_results: Results from process_batch()
            
        Returns:
            List of payloads that should be sent to notification service
        """
        notifications = []
        for decision in batch_results.get('decisions', []):
            if decision['decision'] == 'SEND_NOTIFICATION':
                notifications.append(decision['payload'])
        
        logger.info(f"[GATEWAY] Extracted {len(notifications)} notifications from batch")
        return notifications
