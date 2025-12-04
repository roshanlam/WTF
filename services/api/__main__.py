from services.decision_gateway.__main__ import DecisionGateway
from services.mq_consumer.__main__ import MQConsumer
import json


def main():
    print("API Service Here...")
    gateway = DecisionGateway()
    consumer = MQConsumer()

    # Test cases
    test_tweets = [
        {
            'club_name': 'Computer Science Club',
            'tweet': 'Join us for our weekly meeting tomorrow at 6pm in CS Building Room 101! Free pizza and drinks will be provided.',
            'food_label': 1
        },
        {
            'club_name': 'Debate Society',
            'tweet': 'Practice session this Thursday at 7pm. Bring your topics and arguments!',
            'food_label': 0
        },
        {
            'club_name': 'Engineering Club',
            'tweet': 'Career fair TODAY at Student Union, 2-5pm. Free snacks and refreshments for all attendees!',
            'food_label': 1
        }
    ]
    
    print("=" * 80)
    print("Testing Single Tweet Processing")
    print("=" * 80)
    
    result = gateway.process_tweet(test_tweets[0])
    print(json.dumps(result, indent=2))
    
    # print("\n" + "=" * 80)
    # print("Testing Batch Processing")
    # print("=" * 80)
    
    # batch_results = gateway.process_batch(test_tweets)
    # print(json.dumps({
    #     'total_processed': batch_results['total_processed'],
    #     'notifications_to_send': batch_results['notifications_to_send'],
    #     'no_action': batch_results['no_action'],
    #     'errors': batch_results['errors']
    # }, indent=2))
    
    # print("\n" + "=" * 80)
    # print("Notifications to Send")
    # print("=" * 80)
    
    # notifications = gateway.get_notifications_from_batch(batch_results)
    # for notif in notifications:
    #     print(f"\nClub: {notif['club_name']}")
    #     print(f"Event: {notif.get('event_details', {}).get('title', 'N/A')}")
    #     print(f"Confidence: {notif['confidence']:.2f}")

if __name__ == "__main__":
    main()
