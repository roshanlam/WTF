import os
import time
import json
import requests
import concurrent.futures
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()


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
        
        tweet = row_data.get('tweet', '')
        ground_truth = int(row_data.get('food_label', 0))
        
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
  → food_available: true, title: "Workshop", location: "Integrative Learning Center", start_time: "2025-08-23T00:00:00" """
                },
                {
                    "role": "user", 
                    "content": f"Club: {row_data.get('club_name', 'Unknown')}\nTweet: {tweet}"
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "type": "object",
                    "properties": {
                        "food_available": {
                            "type": "boolean",
                            "description": "True only if food/drinks/snacks are explicitly mentioned as being provided"
                        },
                        "title": {
                            "type": "string",
                            "description": "The event title/name. Only include if food_available is true."
                        },
                        "location": {
                            "type": "string",
                            "description": "The location where the event will take place. Only include if food_available is true."
                        },
                        "start_time": {
                            "type": "string",
                            "description": "The date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS). Only include if food_available is true."
                        },
                        "llm_confidence": {
                            "type": "number",
                            "description": "Confidence score between 0.0 and 1.0 indicating certainty of food availability detection",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why food was or wasn't detected"
                        }
                    },
                    "required": ["food_available", "llm_confidence", "reason"]
                }
            }
        }

        response = requests.post(
            api_url,
            headers=HEADERS,
            json=payload,
            timeout=45
        )

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
                    result['club_name'] = row_data.get('club_name', 'Unknown')
                    
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