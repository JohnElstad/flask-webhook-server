# Flask Webhook Server

A Flask-based webhook server designed to receive and process webhooks from GoHighLevel (GHL) and other services.

## Features

- **Webhook Endpoint**: `/webhook` - Receives POST requests from external services
- **Message Batching**: Automatically batches incoming messages and processes them together for better AI context
- **Configurable Wait Time**: Adjustable batch wait time (default: 30 seconds) via environment variable or API
- **Health Check**: `/health` - Verify server status
- **Test Endpoint**: `/test-webhook` - Test webhook functionality
- **Comprehensive Logging**: All webhook requests are logged for debugging
- **Error Handling**: Robust error handling with detailed logging
- **CORS Support**: Cross-origin requests enabled for testing

## Project Structure

```
src/
├── app.py              # Main Flask application
├── routes.py           # Webhook routes and handlers
├── requirements.txt    # Python dependencies
├── env.example        # Environment variables template
└── README.md          # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd src
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the environment template and configure your settings:

```bash
cp env.example .env
```

Edit `.env` with your configuration:
- `HOST`: Server host (127.0.0.1 for local, 0.0.0.0 for production)
- `PORT`: Server port (default: 5000)
- `WEBHOOK_SECRET`: Secret key for webhook verification
- `GHL_API_KEY`: Your GoHighLevel API key
- `GHL_LOCATION_ID`: Your GHL location ID

### 3. Run the Server

```bash
python app.py
```

The server will start on `http://127.0.0.1:5000` by default.

## Testing Your Webhook

### Local Testing

1. **Start the server**:
   ```bash
   python app.py
   ```

2. **Test the endpoints**:
   - Health check: `http://127.0.0.1:5000/health`
   - Test webhook: `http://127.0.0.1:5000/test-webhook`

3. **Send a test webhook**:
   ```bash
   curl -X POST http://127.0.0.1:5000/webhook \
     -H "Content-Type: application/json" \
     -d '{"type": "contact.reply", "contact": {"id": "123"}, "message": "test"}'
   ```

### Internet-Accessible Testing

To receive webhooks from external services (like GHL), you need to make your local server accessible from the internet.

#### Option 1: ngrok (Recommended for development)

1. **Install ngrok** from [ngrok.com](https://ngrok.com)
2. **Start your Flask app** (keep it running)
3. **In another terminal, expose your local server**:
   ```bash
   ngrok http 5000
   ```
4. **Use the ngrok URL** as your webhook endpoint in GHL:
   ```
   https://abc123.ngrok.io/webhook
   ```

#### Option 2: Deploy to Cloud

- **Heroku**: `git push heroku main`
- **Railway**: Connect your GitHub repo
- **Render**: Connect your GitHub repo

## Webhook Endpoints

### POST /webhook

Receives webhook data from external services.

**Expected Data Format**:
```json
{
  "type": "contact.reply",
  "contact": {
    "id": "contact_id_here"
  },
  "message": {
    "content": "message content"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "timestamp": "2024-01-01T12:00:00"
}
```

### GET /health

Health check endpoint to verify server status.

### GET /test-webhook

Test endpoint to verify webhook functionality.

## Message Batching System

The server now includes an intelligent message batching system that waits for user messages to accumulate before processing them with AI. This provides better context and more coherent responses.

### How It Works

1. **Message Reception**: When a webhook is received, the message is immediately stored in Supabase
2. **Batch Creation**: A new batch is started for the contact (or existing batch is extended)
3. **Wait Period**: The system waits for a configurable time period (default: 30 seconds)
4. **Batch Processing**: If no new messages arrive during the wait period, all messages in the batch are processed together
5. **AI Response**: OpenAI generates a single response considering all messages in context

### Benefits

- **Better Context**: AI can see multiple related messages together
- **Reduced API Calls**: Fewer OpenAI API calls for conversation threads
- **Improved Responses**: More coherent and contextual AI responses
- **User Experience**: Users can send multiple short messages without getting fragmented responses

### Configuration

#### Environment Variable
```bash
MESSAGE_BATCH_WAIT_TIME=30  # seconds (5-300 seconds allowed)
```

#### API Configuration
```bash
# Get current batch configuration
GET /batch-config

# Update batch wait time
POST /batch-config
{
  "batch_wait_time": 45
}
```

### Batch Management Endpoints

#### GET /queue-status
Check the status of all active message batches.

#### POST /force-process-batch/{contact_id}
Force process a batch immediately without waiting for the timer.

#### GET /batch-status/{contact_id}
Get detailed information about a specific contact's batch.

### Example Workflow

1. User sends: "Hi there"
2. User sends: "I have a question"
3. User sends: "About gym membership"
4. After 30 seconds of no new messages, AI processes all three messages together
5. AI responds with a comprehensive answer considering the full context

### Batch Status Response
```json
{
  "status": "success",
  "active_batches": 2,
  "batch_details": {
    "contact_123": {
      "batch_id": "batch_contact_123_1704067200",
      "start_time": "2024-01-01T12:00:00Z",
      "last_message_time": "2024-01-01T12:00:15Z",
      "message_count": 3,
      "messages": ["Hi there", "I have a question", "About gym membership"],
      "time_remaining": 15
    }
  },
  "batch_wait_time": 30,
  "timestamp": "2024-01-01T12:00:15Z"
}
```

## Supported Webhook Types

- `contact.reply` - When a contact replies to a message
- `contact.created` - When a new contact is created
- `unknown` - Any other webhook type (logged but not processed)

## Logging

All webhook requests are logged with:
- Timestamp
- Request data
- Headers
- Processing results
- Any errors that occur

Check your terminal output for detailed logs.

## Customization

### Adding New Webhook Types

1. Add a new handler function in `routes.py`
2. Update the main webhook function to route to your handler
3. Add your business logic

### Business Logic

The webhook handlers are designed to be easily extended. Add your specific business logic in the handler functions:
- Database operations
- API calls to other services
- Email notifications
- Status updates

## Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in `.env` or kill the process using the port
2. **CORS errors**: The server includes CORS support, but check your browser console
3. **Webhook not received**: Verify the URL is correct and accessible from the internet
4. **JSON parsing errors**: Check the webhook payload format

### Debug Mode

The server runs in debug mode by default. Check the terminal for detailed error messages and request logs.

## Security Considerations

- Use HTTPS in production
- Implement webhook signature verification
- Rate limiting for production use
- Environment variable management
- Input validation and sanitization

## Production Deployment

For production use:
1. Set `HOST=0.0.0.0` to bind to all interfaces
2. Use a production WSGI server like Gunicorn
3. Set up proper logging
4. Implement webhook verification
5. Use environment variables for configuration
6. Set up monitoring and alerting 