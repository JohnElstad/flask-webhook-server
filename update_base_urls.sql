-- Update all subaccounts to use the new GHL API base URL
-- Run this in your Supabase SQL Editor

UPDATE subaccounts 
SET ghl_base_url = 'https://services.leadconnectorhq.com',
    updated_at = NOW()
WHERE ghl_base_url IS NULL 
   OR ghl_base_url = '' 
   OR ghl_base_url = 'https://rest.gohighlevel.com/v1';

-- Verify the update
SELECT subaccount_id, subaccount_name, ghl_base_url, updated_at 
FROM subaccounts 
ORDER BY updated_at DESC;
