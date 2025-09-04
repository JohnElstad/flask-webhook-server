-- Create the server_logs table for storing application logs
CREATE TABLE IF NOT EXISTS server_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(10) NOT NULL,
    logger_name VARCHAR(255),
    message TEXT NOT NULL,
    module VARCHAR(255),
    function VARCHAR(255),
    line_number INTEGER,
    process_id INTEGER,
    thread_id BIGINT,
    thread_name VARCHAR(255),
    exception_type VARCHAR(255),
    exception_message TEXT,
    traceback TEXT,
    contact_id VARCHAR(255),
    webhook_type VARCHAR(100),
    operation VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_server_logs_timestamp ON server_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_server_logs_level ON server_logs(level);
CREATE INDEX IF NOT EXISTS idx_server_logs_contact_id ON server_logs(contact_id);
CREATE INDEX IF NOT EXISTS idx_server_logs_webhook_type ON server_logs(webhook_type);
CREATE INDEX IF NOT EXISTS idx_server_logs_operation ON server_logs(operation);

-- Create a function to automatically clean old logs (optional)
-- This will delete logs older than 30 days
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM server_logs 
    WHERE timestamp < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Create a cron job to run cleanup every day at 2 AM (optional)
-- Note: This requires the pg_cron extension to be enabled in Supabase
-- SELECT cron.schedule('cleanup-old-logs', '0 2 * * *', 'SELECT cleanup_old_logs();');

-- Grant permissions (adjust as needed for your setup)
GRANT ALL ON server_logs TO authenticated;
GRANT USAGE ON SEQUENCE server_logs_id_seq TO authenticated;

-- Create a view for recent logs (last 24 hours)
CREATE OR REPLACE VIEW recent_logs AS
SELECT 
    timestamp,
    level,
    logger_name,
    message,
    contact_id,
    webhook_type,
    operation
FROM server_logs 
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- Create a view for error logs
CREATE OR REPLACE VIEW error_logs AS
SELECT 
    timestamp,
    logger_name,
    message,
    exception_type,
    exception_message,
    contact_id,
    webhook_type,
    operation
FROM server_logs 
WHERE level IN ('ERROR', 'CRITICAL')
ORDER BY timestamp DESC;

-- Create a view for contact-specific logs
CREATE OR REPLACE VIEW contact_logs AS
SELECT 
    timestamp,
    level,
    logger_name,
    message,
    webhook_type,
    operation
FROM server_logs 
WHERE contact_id IS NOT NULL
ORDER BY contact_id, timestamp DESC;

-- Example queries for monitoring:

-- Get log count by level for the last hour
-- SELECT level, COUNT(*) as count 
-- FROM server_logs 
-- WHERE timestamp > NOW() - INTERVAL '1 hour' 
-- GROUP BY level 
-- ORDER BY count DESC;

-- Get recent errors for a specific contact
-- SELECT timestamp, message, exception_message 
-- FROM server_logs 
-- WHERE level = 'ERROR' 
-- AND contact_id = 'your_contact_id' 
-- ORDER BY timestamp DESC 
-- LIMIT 10;

-- Get webhook processing statistics
-- SELECT 
--     webhook_type,
--     COUNT(*) as total_requests,
--     COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as errors,
--     ROUND(
--         COUNT(CASE WHEN level = 'ERROR' THEN 1 END)::DECIMAL / COUNT(*) * 100, 2
--     ) as error_rate_percent
-- FROM server_logs 
-- WHERE webhook_type IS NOT NULL 
-- AND timestamp > NOW() - INTERVAL '24 hours'
-- GROUP BY webhook_type 
-- ORDER BY total_requests DESC;
