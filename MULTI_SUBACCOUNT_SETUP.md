# Multi-Subaccount Setup Guide

This guide explains how to configure your Flask webhook server to work with multiple GoHighLevel (GHL) subaccounts.

## Overview

The multi-subaccount system allows you to:
- Handle webhooks from multiple GHL subaccounts
- Route messages using the correct API credentials for each subaccount
- Store data with subaccount context for proper isolation
- Manage subaccount configurations via API endpoints

## Architecture

### Components

1. **SubaccountManager**: Handles credential management and subaccount detection
2. **Database Schema**: Extended to include subaccount information
3. **Webhook Handler**: Updated to identify and route by subaccount
4. **Chat Processor**: Uses subaccount-specific credentials for GHL API calls
5. **Management API**: Endpoints for configuring subaccounts

### Data Flow

1. Webhook received → Extract subaccount ID from payload
2. Look up credentials for subaccount → Fallback to default if not found
3. Process message with subaccount context
4. Store data with subaccount_id
5. Send response using subaccount-specific API credentials

## Setup Instructions

### 1. Database Setup

Run the multi-subaccount database migration:

```sql
-- Run this in your Supabase SQL Editor
-- (Contents of setup_multi_subaccount_tables.sql)
```

This will:
- Create `subaccounts` table for storing credentials
- Add `subaccount_id` columns to existing tables
- Set up proper indexes and relationships

### 2. Environment Variables

Update your `.env` file to include default fallback credentials:

```env
# Default GHL Configuration (fallback)
GHL_API_KEY=your_default_ghl_api_key_here
GHL_LOCATION_ID=your_default_location_id_here
GHL_BASE_URL=https://rest.gohighlevel.com/v1

# Supabase Configuration (required)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Other existing configuration...
```

### 3. Add Subaccounts

Use the API endpoints to add your subaccounts:

#### Method 1: API Endpoint

```bash
curl -X POST http://your-server.com/api/subaccounts \
  -H "Content-Type: application/json" \
  -d '{
    "subaccount_id": "sub_account_1",
    "subaccount_name": "Main Business Account",
    "ghl_api_key": "your_api_key_1",
    "ghl_location_id": "your_location_id_1",
    "ghl_base_url": "https://rest.gohighlevel.com/v1"
  }'
```

#### Method 2: Direct Database Insert

```sql
INSERT INTO subaccounts (subaccount_id, subaccount_name, ghl_api_key, ghl_location_id) 
VALUES 
    ('sub_account_1', 'Main Business Account', 'your_api_key_1', 'your_location_id_1'),
    ('sub_account_2', 'Secondary Business Account', 'your_api_key_2', 'your_location_id_2');
```

### 4. Configure GHL Webhooks

In each GHL subaccount, set up webhooks to point to your server:

**Webhook URL**: `https://your-server.com/webhook`

**Important**: Ensure your GHL webhooks include the location ID in the payload. This is typically included automatically in fields like:
- `locationId`
- `location_id`
- `customData.locationId`

## API Endpoints

### Subaccount Management

#### List Subaccounts
```http
GET /api/subaccounts
```

Response:
```json
{
  "status": "success",
  "subaccounts": [
    {
      "subaccount_id": "sub_account_1",
      "subaccount_name": "Main Business Account",
      "ghl_location_id": "loc_123",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

#### Add Subaccount
```http
POST /api/subaccounts
Content-Type: application/json

{
  "subaccount_id": "sub_account_1",
  "subaccount_name": "Main Business Account",
  "ghl_api_key": "your_api_key_here",
  "ghl_location_id": "your_location_id_here",
  "ghl_base_url": "https://rest.gohighlevel.com/v1"
}
```

#### Get Subaccount Info
```http
GET /api/subaccounts/{subaccount_id}
```

#### Test Subaccount Credentials
```http
POST /api/subaccounts/test/{subaccount_id}
```

#### Test Webhook Subaccount Detection
```http
POST /api/webhook/test
Content-Type: application/json

{
  "locationId": "sub_account_1",
  "contact_id": "test_contact",
  "message": {
    "body": "Test message"
  }
}
```

## Subaccount Detection

The system attempts to extract subaccount ID from webhook payloads in this order:

1. `locationId` (most common)
2. `location_id`
3. `customData.locationId`
4. `customData.subaccountId`
5. `customData.location_id`
6. `contact.locationId`
7. `contact.location_id`
8. `message.locationId`
9. `message.location_id`
10. Any field containing 'location' in the key name

If no subaccount ID is found, the system falls back to default credentials.

## Troubleshooting

### 1. Check Subaccount Detection

Test webhook subaccount detection:

```bash
curl -X POST http://your-server.com/api/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "locationId": "your_subaccount_id",
    "contact_id": "test_contact",
    "message": {"body": "test"}
  }'
```

### 2. Test Subaccount Credentials

```bash
curl -X POST http://your-server.com/api/subaccounts/test/your_subaccount_id
```

### 3. Check Logs

Monitor your server logs for subaccount-related messages:
- `Extracted subaccount ID: {subaccount_id}`
- `No credentials found for subaccount {subaccount_id}, falling back to default`
- `Using subaccount-specific credentials for {subaccount_id}`

### 4. Verify Database

Check that subaccounts are properly stored:

```sql
SELECT * FROM subaccounts WHERE is_active = true;
```

### 5. Common Issues

**Issue**: Webhooks not detecting subaccount
- **Solution**: Check that GHL webhooks include `locationId` in payload
- **Debug**: Use `/api/webhook/test` endpoint with actual webhook data

**Issue**: Credentials not found
- **Solution**: Verify subaccount exists in database and is active
- **Debug**: Check `/api/subaccounts` endpoint

**Issue**: API calls failing
- **Solution**: Test credentials with `/api/subaccounts/test/{id}`
- **Check**: Ensure API keys have proper permissions

## Migration from Single Account

If you're migrating from a single-account setup:

1. **Backup your data** before running migrations
2. **Run the database migration** to add subaccount support
3. **Add your existing account** as the default subaccount
4. **Test thoroughly** with existing webhooks
5. **Add additional subaccounts** as needed

### Migration Script Example

```sql
-- Add your existing account as default subaccount
INSERT INTO subaccounts (subaccount_id, subaccount_name, ghl_api_key, ghl_location_id)
VALUES ('default', 'Default Account', 'your_existing_api_key', 'your_existing_location_id');

-- Update existing contacts and messages to use default subaccount
UPDATE contacts SET subaccount_id = 'default' WHERE subaccount_id IS NULL;
UPDATE messages SET subaccount_id = 'default' WHERE subaccount_id IS NULL;
```

## Security Considerations

1. **API Key Storage**: API keys are stored in the database. Ensure your Supabase instance is properly secured.
2. **Access Control**: Consider implementing authentication for the management API endpoints.
3. **Environment Variables**: Keep default credentials in environment variables as a fallback.
4. **Logging**: API keys are masked in logs and API responses for security.

## Performance Notes

1. **Credential Caching**: Subaccount credentials are cached for 5 minutes to reduce database queries.
2. **Database Indexes**: Proper indexes are created for subaccount lookups.
3. **Fallback Strategy**: Default credentials provide fast fallback when subaccount detection fails.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review server logs for error messages
3. Test individual components using the provided API endpoints
4. Verify your GHL webhook configuration includes location information
