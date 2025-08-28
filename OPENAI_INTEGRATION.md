# OpenAI Integration with Sliding Window Timer

This document explains the OpenAI integration and sliding window timer functionality added to the Flask Webhook Server.

## Overview

The system now implements a **30-second sliding window timer** that waits for additional SMS messages before processing them with OpenAI. This prevents rapid-fire responses and allows for more context-aware AI interactions.

## How It Works

1. **SMS Received**: When an SMS is received via webhook, it's stored in Supabase
2. **Timer Started**: A 30-second timer is started/reset for that contact
3. **Additional SMS**: If another SMS arrives within 30 seconds, the timer resets
4. **Window Expires**: After 30 seconds of no new SMS, the system:
   - Retrieves chat history from Supabase
   - Sends the conversation context to OpenAI
   - Generates an AI response
   - Stores the response in Supabase

## Features

### Sliding Window Timer
- **Duration**: 30 seconds (configurable)
- **Per Contact**: Each contact has their own independent timer
- **Auto-reset**: Timer resets when new SMS arrives
- **Thread-safe**: Uses threading locks for concurrent access

### OpenAI Integration
- **Sentiment Analysis**: Analyzes message sentiment (positive/negative/neutral)
- **Intent Classification**: Identifies message intent (support, booking, inquiry, etc.)
- **AI Response Generation**: Creates contextual responses based on chat history
- **Token Tracking**: Monitors OpenAI API usage

### Chat History Processing
- **Context Awareness**: Includes previous conversation context
- **Chronological Order**: Messages are processed in time order
- **Multi-message Support**: Handles conversations with multiple exchanges

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
```

### Supabase Setup

Run the SQL script `setup_openai_tables.sql` in your Supabase SQL editor to create the necessary tables and functions.

## API Endpoints

### Main Webhook
- **POST** `/webhook` - Receives SMS and starts sliding window timer

### Timer Management
- **GET** `/timers` - View active sliding window timers
- **POST** `/cancel-timer` - Cancel timer for a specific contact
- **POST** `/process-chat` - Manually trigger chat processing

### OpenAI Testing
- **POST** `/test-openai` - Test OpenAI functionality
- **POST** `/analyze-sentiment` - Analyze message sentiment
- **POST** `/generate-response` - Generate AI response

### Configuration
- **GET** `/config` - Check system configuration status

## Usage Examples

### 1. Send SMS and Start Timer

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "12345",
    "message": {
      "body": "Hello, I need help with my order"
    },
    "first_name": "John",
    "last_name": "Doe"
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Webhook processed successfully - 30-second sliding window timer started",
  "contact_id": "12345",
  "sliding_window": {
    "active": true,
    "duration_seconds": 30,
    "message": "Timer started - waiting for additional SMS messages"
  }
}
```

### 2. Check Active Timers

```bash
curl http://localhost:5000/timers
```

**Response:**
```json
{
  "status": "success",
  "active_timers": {
    "12345": 30
  },
  "timer_count": 1
}
```

### 3. Manually Process Chat

```bash
curl -X POST http://localhost:5000/process-chat \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "12345"
  }'
```

### 4. Test OpenAI Directly

```bash
curl -X POST http://localhost:5000/test-openai \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need help with my order",
    "contact_info": {
      "first_name": "John",
      "last_name": "Doe"
    }
  }'
```

## Database Schema

### Messages Table
Stores all SMS messages and AI responses:

```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    contact_id TEXT NOT NULL,
    message_body TEXT NOT NULL,
    message_type TEXT DEFAULT 'SMS', -- 'SMS' or 'AI_RESPONSE'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB -- Additional metadata for AI responses
);
```

### OpenAI Analysis Table
Stores detailed analysis results:

```sql
CREATE TABLE openai_analysis (
    id SERIAL PRIMARY KEY,
    contact_id TEXT NOT NULL,
    message_body TEXT NOT NULL,
    sentiment TEXT,
    sentiment_confidence DECIMAL(3,2),
    intent TEXT,
    ai_response TEXT,
    tokens_used INTEGER,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Flow Diagram

```
SMS Received
     ↓
Store in Supabase
     ↓
Start/Reset 30s Timer
     ↓
Wait for Additional SMS
     ↓
[New SMS?] → Yes → Reset Timer
     ↓ No
Timer Expires
     ↓
Get Chat History
     ↓
Send to OpenAI
     ↓
Generate Response
     ↓
Store AI Response
     ↓
[Optional] Send SMS Response
```

## Error Handling

The system includes comprehensive error handling:

- **OpenAI API Errors**: Graceful fallback if OpenAI is unavailable
- **Supabase Errors**: Logs errors but continues operation
- **Timer Errors**: Automatic cleanup of failed timers
- **Network Errors**: Retry logic for API calls

## Monitoring

### Logs
The system logs all important events:
- Timer starts/resets
- Chat history retrieval
- OpenAI API calls
- Response generation
- Error conditions

### Metrics
Track these metrics for monitoring:
- Active timer count
- OpenAI API usage (tokens)
- Response generation time
- Error rates

## Troubleshooting

### Common Issues

1. **Timer Not Starting**
   - Check if contact_id is provided in webhook
   - Verify threading is working properly

2. **OpenAI Not Responding**
   - Verify OPENAI_API_KEY is set
   - Check OpenAI API quota/limits
   - Review API response logs

3. **Chat History Not Found**
   - Verify Supabase connection
   - Check if messages are being stored
   - Review contact_id format

### Debug Endpoints

Use these endpoints for debugging:
- `/config` - Check all configurations
- `/timers` - View active timers
- `/health` - Basic health check

## Security Considerations

- **API Keys**: Store securely in environment variables
- **Rate Limiting**: Implement rate limiting for OpenAI calls
- **Input Validation**: Validate all webhook inputs
- **Error Messages**: Don't expose sensitive information in errors

## Performance Optimization

- **Connection Pooling**: Reuse database connections
- **Caching**: Cache frequently accessed chat history
- **Async Processing**: Consider async for OpenAI calls
- **Batch Processing**: Process multiple messages together

## Future Enhancements

- **Custom Timer Durations**: Per-contact timer configuration
- **Smart Context**: Intelligent context selection
- **Response Templates**: Pre-defined response templates
- **Analytics Dashboard**: Real-time monitoring interface
- **SMS Sending**: Automatic SMS response sending
