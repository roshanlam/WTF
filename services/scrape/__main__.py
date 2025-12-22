#!/usr/bin/env python3
"""
UMass Events Calendar Scraper - API Version
Uses the Localist API to fetch events from https://events.umass.edu
Much more reliable than HTML scraping!
"""

import requests
from datetime import datetime, timedelta
import json
import logging
import sys
from typing import List, Dict, Optional
from pathlib import Path

# Configuration
BASE_URL = "https://events.umass.edu"
API_URL = f"{BASE_URL}/api/2/events"
OUTPUT_DIR = Path("./events_data")
LOG_FILE = OUTPUT_DIR / "scraper.log"

# Setup logging
OUTPUT_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class UMassEventsScraper:
    """Scraper for UMass Amherst Events Calendar using Localist API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_events(self, days_ahead: int = 7, per_page: int = 100) -> List[Dict]:
        """
        Fetch events from the Localist API
        
        Args:
            days_ahead: Number of days ahead to fetch (max 370)
            per_page: Results per page (max 100)
        """
        all_events = []
        page = 1
        
        while True:
            params = {
                'days': min(days_ahead, 370),  # API max is 370 days
                'pp': per_page,  # per page
                'page': page
            }
            
            try:
                logger.info(f"Fetching page {page} from API...")
                response = self.session.get(API_URL, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract events from the response
                events = data.get('events', [])
                
                if not events:
                    logger.info(f"No more events found on page {page}")
                    break
                
                logger.info(f"Found {len(events)} events on page {page}")
                
                # Process each event
                for event_data in events:
                    processed_event = self.process_event(event_data)
                    if processed_event:
                        all_events.append(processed_event)
                
                # Check if there are more pages
                page_info = data.get('page', {})
                total_pages = page_info.get('total', 1)
                
                if page >= total_pages:
                    logger.info(f"Reached last page ({total_pages})")
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        return all_events
    
    def process_event(self, event_data: Dict) -> Optional[Dict]:
        """Process and clean event data from API response"""
        try:
            event = event_data.get('event', {})
            
            # Extract basic info
            processed = {
                'id': event.get('id'),
                'title': event.get('title', ''),
                'description': event.get('description', ''),
                'description_text': event.get('description_text', ''),  # Plain text version
                'url': event.get('localist_url', ''),
                'created_at': event.get('created_at'),
                'updated_at': event.get('updated_at'),
                'scraped_at': datetime.now().isoformat(),
            }
            
            # Event instances (dates/times)
            instances = event.get('event_instances', [])
            processed['instances'] = []
            for instance in instances:
                inst_data = instance.get('event_instance', {})
                processed['instances'].append({
                    'start': inst_data.get('start'),
                    'end': inst_data.get('end'),
                    'all_day': inst_data.get('all_day', False)
                })
            
            # Location information
            location = event.get('location', {})
            if location:
                processed['location'] = {
                    'name': event.get('location_name', ''),
                    'address': event.get('address', ''),
                    'room': event.get('room_number', ''),
                    'geo': event.get('geo', {})
                }
            else:
                processed['location'] = None
            
            # Event filters (types, topics, audience)
            filters = event.get('filters', {})
            processed['event_types'] = [t.get('name') for t in filters.get('event_types', [])]
            processed['event_audience'] = [a.get('name') for a in filters.get('event_audience', [])]
            
            # Event topics - might be in different fields
            topics = []
            for key in ['event_topic', 'topics', 'departments']:
                if key in filters:
                    topics.extend([t.get('name') for t in filters.get(key, [])])
            processed['topics'] = topics
            
            # Photo
            processed['photo_url'] = event.get('photo_url', '')
            
            # Free event detection
            processed['cost'] = event.get('ticket_cost', '')
            processed['is_free'] = self.detect_free_event(event)
            
            # Contact info
            processed['contact_email'] = event.get('contact_email', '')
            processed['contact_phone'] = event.get('contact_phone', '')
            
            # Custom fields
            processed['custom_fields'] = event.get('custom_fields', {})
            
            # Experience (virtual/in-person)
            processed['experience'] = event.get('experience', '')
            
            # Group/Department
            group = event.get('group', {})
            processed['group'] = group.get('name', '') if group else ''
            
            # Featured event
            processed['featured'] = event.get('featured', False)
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None
    
    def detect_free_event(self, event: Dict) -> bool:
        """Detect if an event is free"""
        # Check ticket cost
        cost = event.get('ticket_cost', '').lower()
        if cost in ['free', 'free!', '']:
            return True
        
        # Check for $0
        if '$0' in cost or cost == '0':
            return True
        
        # Check description for "free" mentions
        description = event.get('description_text', '').lower()
        if 'free admission' in description or 'admission is free' in description:
            return True
        
        return False
    
    def detect_food_events(self, events: List[Dict]) -> List[Dict]:
        """Filter events that likely have free food"""
        food_keywords = [
            'food', 'free food', 'refreshments', 'snacks', 'lunch', 
            'dinner', 'breakfast', 'pizza', 'coffee', 'cookies',
            'catering', 'meal', 'eat', 'beverages', 'drinks',
            'bagels', 'donuts', 'doughnuts', 'tea', 'reception'
        ]
        
        food_events = []
        
        for event in events:
            if not event.get('is_free', False):
                continue
            
            # Check title and description
            title = event.get('title', '').lower()
            description = event.get('description_text', '').lower()
            combined_text = f"{title} {description}"
            
            # Check if any food keyword is present
            if any(keyword in combined_text for keyword in food_keywords):
                event['food_confidence'] = 'high' if 'free food' in combined_text else 'medium'
                food_events.append(event)
        
        return food_events
    
    def save_events(self, events: List[Dict], filename: str = None):
        """Save events to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"events_{timestamp}.json"
        
        output_path = OUTPUT_DIR / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(events)} events to {output_path}")
        return output_path


def main():
    """Main execution function"""
    scraper = UMassEventsScraper()
    
    # Fetch events for the next 7 days (you can change this)
    days_ahead = 7
    
    logger.info(f"Starting scrape for next {days_ahead} days")
    
    # Fetch all events
    events = scraper.fetch_events(days_ahead=days_ahead)
    
    if events:
        # Save all events
        output_file = scraper.save_events(events)
        logger.info(f"Successfully scraped {len(events)} events")
        
        # Detect and save free food events
        food_events = scraper.detect_food_events(events)
        if food_events:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            food_file = scraper.save_events(food_events, f"free_food_{timestamp}.json")
            logger.info(f"Found {len(food_events)} potential free food events")
            
            # Print free food events summary
            logger.info("\n" + "="*60)
            logger.info("🍕 FREE FOOD EVENTS DETECTED 🍕")
            logger.info("="*60)
            for event in food_events:
                logger.info(f"\n📅 {event['title']}")
                if event['instances']:
                    start = event['instances'][0]['start']
                    logger.info(f"   ⏰ {start}")
                if event.get('location'):
                    logger.info(f"   📍 {event['location'].get('name', 'Location TBD')}")
                logger.info(f"   🔗 {event['url']}")
                logger.info(f"   🎯 Confidence: {event.get('food_confidence', 'unknown')}")
        
        # Print general summary
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info("="*60)
        logger.info(f"Total events: {len(events)}")
        logger.info(f"Free events: {sum(1 for e in events if e.get('is_free', False))}")
        logger.info(f"Free food events: {len(food_events)}")
        
    else:
        logger.warning("No events found")


if __name__ == "__main__":
    main()