-- Multi-Subaccount Database Setup for Flask Webhook Server
-- Run this in your Supabase SQL Editor

-- Create subaccounts table to store GHL subaccount credentials
CREATE TABLE IF NOT EXISTS subaccounts (
    id SERIAL PRIMARY KEY,
    subaccount_id TEXT UNIQUE NOT NULL,
    subaccount_name TEXT,
    ghl_api_key TEXT NOT NULL,
    ghl_location_id TEXT NOT NULL,
    ghl_base_url TEXT DEFAULT 'https://rest.gohighlevel.com/v1',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Update contacts table to include subaccount_id
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS subaccount_id TEXT;

-- Update messages table to include subaccount_id  
ALTER TABLE messages ADD COLUMN IF NOT EXISTS subaccount_id TEXT;

-- Create foreign key relationships
ALTER TABLE contacts ADD CONSTRAINT fk_contacts_subaccount 
    FOREIGN KEY (subaccount_id) REFERENCES subaccounts(subaccount_id) ON DELETE CASCADE;

ALTER TABLE messages ADD CONSTRAINT fk_messages_subaccount 
    FOREIGN KEY (subaccount_id) REFERENCES subaccounts(subaccount_id) ON DELETE CASCADE;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_subaccounts_subaccount_id ON subaccounts(subaccount_id);
CREATE INDEX IF NOT EXISTS idx_contacts_subaccount_id ON contacts(subaccount_id);
CREATE INDEX IF NOT EXISTS idx_messages_subaccount_id ON messages(subaccount_id);

-- Enable RLS for subaccounts table
ALTER TABLE subaccounts ENABLE ROW LEVEL SECURITY;

-- Create policies for subaccounts table
CREATE POLICY "Allow all operations on subaccounts" ON subaccounts FOR ALL USING (true);

-- Update trigger for subaccounts
CREATE TRIGGER update_subaccounts_updated_at 
    BEFORE UPDATE ON subaccounts 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Sample subaccount data (replace with your actual subaccount info)
-- INSERT INTO subaccounts (subaccount_id, subaccount_name, ghl_api_key, ghl_location_id) 
-- VALUES 
--     ('sub_account_1', 'Main Business Account', 'your_api_key_1', 'your_location_id_1'),
--     ('sub_account_2', 'Secondary Business Account', 'your_api_key_2', 'your_location_id_2');
