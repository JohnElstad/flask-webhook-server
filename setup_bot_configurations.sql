-- Bot Configuration Database Setup
-- Run this in your Supabase SQL Editor

-- Create bot_configurations table
CREATE TABLE IF NOT EXISTS bot_configurations (
    id SERIAL PRIMARY KEY,
    subaccount_id TEXT NOT NULL,
    source_name TEXT NOT NULL,  -- e.g., 'fitness_lead', 'restaurant_booking', 'default'
    bot_name TEXT NOT NULL,     -- Friendly name for the bot
    system_prompt TEXT NOT NULL, -- The system prompt for this bot
    first_message TEXT NOT NULL, -- Initial message to send
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure unique bot per subaccount per source
    UNIQUE(subaccount_id, source_name)
);

-- Create foreign key relationship to subaccounts
ALTER TABLE bot_configurations 
ADD CONSTRAINT fk_bot_configurations_subaccount 
FOREIGN KEY (subaccount_id) REFERENCES subaccounts(subaccount_id) ON DELETE CASCADE;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_bot_configurations_subaccount_id ON bot_configurations(subaccount_id);
CREATE INDEX IF NOT EXISTS idx_bot_configurations_source_name ON bot_configurations(source_name);
CREATE INDEX IF NOT EXISTS idx_bot_configurations_active ON bot_configurations(is_active);

-- Enable RLS
ALTER TABLE bot_configurations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations on bot_configurations" ON bot_configurations FOR ALL USING (true);

-- Update trigger
CREATE TRIGGER update_bot_configurations_updated_at 
    BEFORE UPDATE ON bot_configurations 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Sample bot configurations (replace with your actual bots)
INSERT INTO bot_configurations (subaccount_id, source_name, bot_name, system_prompt, first_message) 
VALUES 
    -- Default bot for Texas Health Fitness Center
    ('Texas Health Fitness Center', 'default', 'Fitness Assistant', 
     'You are a helpful fitness center assistant. Help customers with memberships, classes, and general inquiries.',
     'Hi {name}! Welcome to Texas Health Fitness Center. How can I help you today?'),
    
    -- Fitness lead bot
    ('Texas Health Fitness Center', 'fitness_lead', 'Fitness Lead Bot',
     'You are a fitness lead conversion specialist. Your goal is to convert leads into gym memberships.',
     'Hey {name}! Thanks for your interest in Texas Health Fitness Center. Ready to start your fitness journey?'),
    
    -- Hunt Valley UAPC default bot  
    ('Hunt Valley UAPC', 'default', 'Performance Center Assistant',
     'You are an assistant for Hunt Valley Under Armour Performance Center. Help with training programs and memberships.',
     'Hi {name}! Welcome to Hunt Valley Under Armour Performance Center. How can I assist you?'),
    
    -- Default fallback bot
    ('default', 'default', 'General Assistant',
     'You are a helpful customer service assistant. Provide friendly and professional support.',
     'Hello {name}! How can I help you today?');
