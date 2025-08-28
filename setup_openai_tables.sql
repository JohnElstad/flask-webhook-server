-- OpenAI Integration Tables for Flask Webhook Server
-- Run this in your Supabase SQL editor

-- Create table for OpenAI analysis results
CREATE TABLE IF NOT EXISTS openai_analysis (
    id SERIAL PRIMARY KEY,
    contact_id TEXT NOT NULL,
    message_body TEXT NOT NULL,
    sentiment TEXT,
    sentiment_confidence DECIMAL(3,2),
    intent TEXT,
    ai_response TEXT,
    tokens_used INTEGER,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_openai_analysis_contact_id ON openai_analysis(contact_id);
CREATE INDEX IF NOT EXISTS idx_openai_analysis_created_at ON openai_analysis(created_at);

-- Add AI_RESPONSE message type to existing messages table if not exists
-- (This assumes you already have a messages table from the original setup)
-- If the messages table doesn't exist, you'll need to create it first

-- Update messages table to support AI responses (if needed)
-- ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type TEXT DEFAULT 'SMS';
-- ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Create a view for chat history with AI responses
CREATE OR REPLACE VIEW chat_history_view AS
SELECT 
    contact_id,
    message_body,
    message_type,
    created_at,
    CASE 
        WHEN message_type = 'AI_RESPONSE' THEN 'AI Assistant'
        ELSE 'Customer'
    END as sender_type
FROM messages
ORDER BY contact_id, created_at;

-- Create a function to get recent chat history
CREATE OR REPLACE FUNCTION get_recent_chat_history(
    p_contact_id TEXT,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    contact_id TEXT,
    message_body TEXT,
    message_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    sender_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        chv.contact_id,
        chv.message_body,
        chv.message_type,
        chv.created_at,
        chv.sender_type
    FROM chat_history_view chv
    WHERE chv.contact_id = p_contact_id
    ORDER BY chv.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get conversation summary
CREATE OR REPLACE FUNCTION get_conversation_summary(
    p_contact_id TEXT,
    p_hours_back INTEGER DEFAULT 24
)
RETURNS TABLE (
    total_messages INTEGER,
    customer_messages INTEGER,
    ai_responses INTEGER,
    last_message_at TIMESTAMP WITH TIME ZONE,
    conversation_duration_minutes INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_messages,
        COUNT(CASE WHEN message_type != 'AI_RESPONSE' THEN 1 END)::INTEGER as customer_messages,
        COUNT(CASE WHEN message_type = 'AI_RESPONSE' THEN 1 END)::INTEGER as ai_responses,
        MAX(created_at) as last_message_at,
        EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) / 60::INTEGER as conversation_duration_minutes
    FROM messages
    WHERE contact_id = p_contact_id
    AND created_at >= NOW() - INTERVAL '1 hour' * p_hours_back;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security (RLS) for security
ALTER TABLE openai_analysis ENABLE ROW LEVEL SECURITY;

-- Create policies for openai_analysis table
CREATE POLICY "Enable read access for all users" ON openai_analysis
    FOR SELECT USING (true);

CREATE POLICY "Enable insert access for all users" ON openai_analysis
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update access for all users" ON openai_analysis
    FOR UPDATE USING (true);

-- Create a trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_openai_analysis_updated_at 
    BEFORE UPDATE ON openai_analysis 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing (optional)
-- INSERT INTO openai_analysis (contact_id, message_body, sentiment, sentiment_confidence, intent, ai_response, tokens_used, processed)
-- VALUES 
--     ('test_contact_1', 'Hello, I need help with my order', 'positive', 0.85, 'support', 'I''d be happy to help you with your order!', 45, true),
--     ('test_contact_2', 'This service is terrible', 'negative', 0.92, 'complaint', 'I''m sorry to hear about your experience. Let me help resolve this issue.', 67, true);

-- Grant necessary permissions
GRANT ALL ON openai_analysis TO anon;
GRANT ALL ON openai_analysis TO authenticated;
GRANT USAGE ON SEQUENCE openai_analysis_id_seq TO anon;
GRANT USAGE ON SEQUENCE openai_analysis_id_seq TO authenticated;
