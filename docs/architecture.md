# System Architecture

## Overview

WTF (Where's The Food) is a microservices-based event-driven system for tracking and notifying users about free food events.

## Architecture Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│   API Service   │ (Port 8000)
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ Decision Gateway     │ (Port 8100)
└──────────┬───────────┘
           │
           ▼
    ┌──────────────┐
    │ Redis Stream │
    └──────┬───────┘
           │
    ┌──────┴────────────────────┬──────────────────┐
    ▼                           ▼                  ▼
┌─────────────┐        ┌──────────────┐   ┌────────────────┐
│ LLM Agent   │        │ MQ Consumer  │   │ Notification   │ (Port 8200)
└─────────────┘        └──────────────┘   └────────────────┘
```

## Components

### API Service
- **Port**: 8000
- **Purpose**: Main REST API for external requests
- **Tech**: FastAPI, Uvicorn

### Decision Gateway
- **Port**: 8100
- **Purpose**: Routes requests and applies decision logic
- **Responsibilities**: Request validation, routing, business rules

### LLM Agent
- **Purpose**: AI/LLM processing for intelligent decisions
- **Responsibilities**: Natural language processing, event analysis

### MQ Consumer
- **Purpose**: Consumes events from Redis Stream
- **Responsibilities**: Event processing, job execution

### Notification Service
- **Port**: 8200
- **Purpose**: Sends notifications to users
- **Responsibilities**: Email, SMS, push notifications

## Data Flow

1. Client sends request to API Service
2. API forwards to Decision Gateway
3. Decision Gateway publishes event to Redis Stream
4. Services consume events from stream
5. Notification Service sends alerts to users

## Event Stream

Events are published to Redis Stream: `events.free-food`

### Event Schema

```json
{
  "event_type": "free-food",
  "location": "CS Building Room 140",
  "timestamp": "2025-10-30T12:00:00Z",
  "details": "Pizza in the commons area"
}
```

## Technology Stack

- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Message Queue**: Redis Streams
- **Testing**: Pytest
- **Linting**: Ruff
- **Type Checking**: MyPy

---

## Implementation Status

### Completed ✓
- [x] Message Queue infrastructure
- [x] Consumer with consumer groups
- [x] Schema definition and validation
- [x] MQ Consumer service implementation
- [x] Comprehensive testing
- [x] Documentation

### Future Enhancements
- [ ] Notification Service implementation
- [ ] Database integration for event storage
- [ ] User subscription management
- [ ] Email/SMS notification channels
- [ ] Performance dashboard
- [ ] Dead letter queue for failed messages
- [ ] Message TTL and expiration
- [ ] Monitoring and alerting integration
