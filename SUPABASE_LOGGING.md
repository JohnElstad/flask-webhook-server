# Supabase Logging System

This document explains how to set up and use the new Supabase-based logging system for your Flask webhook server.

## Overview

The new logging system stores all application logs in your Supabase database, providing:
- **Persistent storage** - Logs survive server restarts
- **Rich context** - Each log entry includes contact_id, operation, webhook_type, etc.
- **Searchable** - Query logs by any field using SQL
- **Performance monitoring** - Track errors, response times, and usage patterns
- **Fallback safety** - If Supabase is unavailable, logs fall back to console

## Setup

### 1. Create the Logs Table

Run the SQL script in `setup_logs_table.sql` in your Supabase SQL editor:

```sql
-- Run this in your Supabase SQL editor
\i setup_logs_table.sql
```

This creates:
- `server_logs` table with all necessary fields
- Indexes for fast querying
- Views for common log queries
- Automatic cleanup function (optional)

### 2. Environment Variables

Ensure these are set in your `.env` file:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### 3. Server Configuration

The main server (`flask_webhook_server.py`) automatically sets up logging when it starts.

### 4. Performance Configuration

The logging system is configured for high performance:
- **Batch size**: 20 logs per batch (configurable)
- **Flush interval**: 10 seconds maximum wait time (configurable)
- **Asynchronous**: Logs are queued and sent in background threads
- **Non-blocking**: Your webhook processing won't be slowed down by logging

## Usage

### Basic Logging

```python
from supabase_logger import info_with_context, error_with_context

# Simple info log
info_with_context("Server started successfully")

# Error with context
error_with_context(
    "Failed to process webhook",
    contact_id="contact_123",
    webhook_type="contact.reply",
    operation="webhook_processing"
)
```

### Available Log Levels

```python
from supabase_logger import (
    debug_with_context,    # Detailed debugging info
    info_with_context,     # General information
    warning_with_context,  # Warnings
    error_with_context     # Errors
)
```

### Context Fields

Each log entry can include these context fields:

- `contact_id` - The contact being processed
- `webhook_type` - Type of webhook (e.g., "contact.reply", "contact.created")
- `operation` - What operation is being performed
- `function` - Function name where log was created
- `line` - Line number in source code
- `exc_info` - Exception information (set to `True` for error logs)

## Querying Logs

### Recent Logs (Last 24 Hours)
```sql
SELECT * FROM recent_logs ORDER BY timestamp DESC;
```

### Error Logs Only
```sql
SELECT * FROM error_logs ORDER BY timestamp DESC;
```

### Logs for Specific Contact
```sql
SELECT * FROM server_logs 
WHERE contact_id = 'your_contact_id' 
ORDER BY timestamp DESC;
```

### Webhook Processing Statistics
```sql
SELECT 
    webhook_type,
    COUNT(*) as total_requests,
    COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as errors,
    ROUND(
        COUNT(CASE WHEN level = 'ERROR' THEN 1 END)::DECIMAL / COUNT(*) * 100, 2
    ) as error_rate_percent
FROM server_logs 
WHERE webhook_type IS NOT NULL 
AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY webhook_type 
ORDER BY total_requests DESC;
```

### Performance Monitoring
```sql
-- Find slow operations
SELECT 
    operation,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp)))) as avg_time_between_logs
FROM server_logs 
WHERE operation IS NOT NULL 
AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY operation
ORDER BY avg_time_between_logs DESC;
```

## Benefits

### 1. **Debugging**
- Track exactly what happened with each contact
- See the full context of errors
- Monitor webhook processing flow

### 2. **Monitoring**
- Real-time error rates
- Performance bottlenecks
- Usage patterns

### 3. **Compliance**
- Audit trail of all operations
- Contact-specific activity logs
- Error tracking for support

### 4. **Analytics**
- Webhook success rates
- Peak usage times
- Contact engagement patterns

## Example Integration

Here's how the logging integrates with your existing webhook processing:

```python
def process_webhook(data):
    contact_id = data.get('contact', {}).get('id')
    
    # Log webhook received
    info_with_context(
        "Webhook received",
        contact_id=contact_id,
        webhook_type=data.get('type'),
        operation="webhook_received"
    )
    
    try:
        # Process the webhook
        result = process_contact_data(data)
        
        # Log success
        info_with_context(
            "Webhook processed successfully",
            contact_id=contact_id,
            webhook_type=data.get('type'),
            operation="webhook_processing"
        )
        
        return result
        
    except Exception as e:
        # Log error with full context
        error_with_context(
            f"Failed to process webhook: {str(e)}",
            contact_id=contact_id,
            webhook_type=data.get('type'),
            operation="webhook_processing",
            exc_info=True
        )
        raise
```

## Testing

Run the example script to test the logging system:

```bash
python logging_example.py
```

This will create sample log entries in your Supabase database.

## Performance Testing

Run the performance test to see the improvement:

```bash
python performance_test.py
```

This compares sync vs async logging performance.

## Configuration Options

You can customize the logging performance:

```python
setup_supabase_logging(
    table_name='server_logs',
    log_level=logging.INFO,
    include_console=True,
    batch_size=20,        # Logs per batch (higher = more efficient)
    flush_interval=10.0   # Max seconds to wait (lower = more real-time)
)
```

**Performance tuning:**
- **Higher batch_size**: More efficient, less real-time
- **Lower flush_interval**: More real-time, slightly less efficient
- **Recommended**: batch_size=20, flush_interval=10.0 (good balance)

## Maintenance

### Automatic Cleanup
The system includes an optional cleanup function that removes logs older than 30 days:

```sql
-- Run manually or set up as a cron job
SELECT cleanup_old_logs();
```

### Storage Considerations
- Each log entry is approximately 500-1000 bytes
- 10,000 logs per day ≈ 5-10 MB per day
- Consider adjusting retention period based on your needs

## Troubleshooting

### Logs Not Appearing
1. Check Supabase credentials in `.env`
2. Verify `server_logs` table exists
3. Check console for fallback messages

### Performance Issues
1. Ensure indexes are created
2. Monitor table size
3. Consider log rotation or cleanup

### Missing Context
1. Use `info_with_context()` instead of `logger.info()`
2. Pass relevant context fields
3. Check that context fields are not `None`

## Migration from Console Logging

To migrate existing logging calls:

**Before:**
```python
logger.info(f"Processing contact {contact_id}")
logger.error(f"Error: {str(e)}")
```

**After:**
```python
info_with_context(f"Processing contact {contact_id}", contact_id=contact_id)
error_with_context(f"Error: {str(e)}", contact_id=contact_id, exc_info=True)
```

The system maintains backward compatibility - existing `logger` calls will still work but won't include the rich context.
