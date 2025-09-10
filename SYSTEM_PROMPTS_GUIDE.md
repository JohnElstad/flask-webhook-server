# System Prompts Guide

This guide explains how to use the dynamic system prompts feature that allows different AI responses based on the `sourceforai` field from your GoHighLevel webhook.

## Overview

The system now supports different AI personalities and conversation flows based on how leads were acquired. This allows you to tailor the AI's responses to match the context and expectations of leads from different sources.

## How It Works

1. **Webhook Processing**: When a webhook is received, the system extracts the `sourceforai` field from either:
   - The main webhook data (`data.sourceforai`)
   - The custom data section (`data.customData.sourceforai`)

2. **First Message Selection**: The system automatically selects the appropriate first message based on the `sourceforai` value and stores it in Supabase.

3. **System Prompt Selection**: The system uses the `sourceforai` value to select the appropriate system prompt from the configuration.

4. **AI Response Generation**: The AI generates responses using the selected system prompt, ensuring contextually appropriate conversations.

## Configuration

### System Prompts File

All system prompts and first messages are stored in `system_prompts.py`. The file contains:

- **SYSTEM_PROMPTS Dictionary**: Maps sourceforai values to their corresponding AI system prompts
- **FIRST_MESSAGES Dictionary**: Maps sourceforai values to their corresponding first messages
- **Helper Functions**: For managing and retrieving prompts and first messages
- **Default Fallback**: Uses 'default' prompt and first message when sourceforai is not found

### Available System Prompts

The system comes with pre-configured prompts for common lead sources:

1. **default** - General reactivation campaign (raffle-focused)
2. **facebook** - Facebook leads (welcoming, skip raffle step)
3. **google_ads** - Google Ads leads (professional, highlight features)
4. **referral** - Referred leads (appreciative, special pricing)
5. **website_form** - Website form leads (professional, schedule tour)
6. **event_expo** - Event/expo leads (familiar, special event pricing)
7. **cold_outreach** - Cold outreach (friendly but not pushy)

## Adding New System Prompts

### Method 1: Direct Edit

Edit `system_prompts.py` and add new entries to the `SYSTEM_PROMPTS` dictionary:

```python
SYSTEM_PROMPTS = {
    # ... existing prompts ...
    
    "instagram": """You are an AI SMS assistant for FX Wells Gym. This lead came from Instagram.
    
    Your goals are:
    1) Thank them for following us on Instagram
    2) Highlight our gym's visual appeal and social media presence
    3) Offer a special Instagram follower discount
    4) Get them to visit the gym
    
    Rules:
    - Tone: Trendy, social media savvy, use emojis sparingly
    - Keep messages under 2 sentences
    - If they reply STOP, opt them out immediately
    - If they decline, thank them warmly and end the conversation
    
    Conversation Flow:
    1) Welcome: "Hey! Thanks for following us on Instagram. Love your fitness journey! 💪"
    2) Highlight social aspect: "We post daily workout tips and member transformations on our IG"
    3) Offer special: "Want 20% off your first month as an Instagram follower?"
    4) If yes: Provide details about visiting and claiming the discount
    5) If no: Thank them and end conversation
    
    Gym Details:
    Hunt Valley location of the Under Armour Performance Center
    11270 Pepper Rd, Hunt Valley, MD 21031
    Instagram: @fxwellsgym
    """,
}
```

### Method 2: Programmatic Addition

Use the helper functions in your code:

```python
from system_prompts import add_system_prompt

# Add a new prompt
success = add_system_prompt('tiktok', 'Your custom prompt here...')
if success:
    print("Prompt added successfully")
```

## Webhook Integration

### GoHighLevel Setup

In your GoHighLevel webhook, include the `sourceforai` field in your custom data:

```json
{
  "contact_id": "12345",
  "message": {
    "body": "Hi, I'm interested in joining"
  },
  "customData": {
    "sourceforai": "facebook"
  }
}
```

### Alternative: Main Data Field

You can also include it in the main webhook data:

```json
{
  "contact_id": "12345",
  "message": {
    "body": "Hi, I'm interested in joining"
  },
  "sourceforai": "google_ads"
}
```

## Testing

### Test Different Sources

You can test different sourceforai values by sending webhooks with different values:

```bash
# Test Facebook lead
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "test123",
    "message": {"body": "Hi, I saw your gym on Facebook"},
    "customData": {"sourceforai": "facebook"}
  }'

# Test Google Ads lead
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "test456",
    "message": {"body": "I found you on Google"},
    "customData": {"sourceforai": "google_ads"}
  }'
```

### Verify System Prompt Usage

Check the logs to see which system prompt is being used:

```
INFO: Using system prompt for sourceforai: facebook
INFO: Using system prompt for sourceforai: google_ads
INFO: Using system prompt for sourceforai: default
```

## Best Practices

### 1. Consistent Naming

Use lowercase, descriptive names for sourceforai values:
- ✅ `facebook`, `google_ads`, `instagram`
- ❌ `Facebook Lead`, `GOOGLE_ADS`, `insta_lead`

### 2. Clear Prompt Structure

Structure your prompts with:
- Clear goals and objectives
- Specific conversation flows
- Consistent rules and tone
- Relevant gym details

### 3. Fallback Handling

Always test with unknown sourceforai values to ensure the default prompt is used appropriately.

### 4. Regular Updates

Review and update prompts based on:
- Performance metrics
- Lead feedback
- Business changes
- New lead sources

## Troubleshooting

### Common Issues

1. **Default Prompt Used**: Check if sourceforai is being passed correctly in webhook data
2. **Case Sensitivity**: The system is case-insensitive, but use consistent naming
3. **Partial Matching**: The system supports partial matching (e.g., `facebook_lead` matches `facebook`)

### Debug Logging

Enable debug logging to see:
- Which sourceforai value is extracted
- Which system prompt is selected
- Message formatting details

### Verification Commands

```python
from system_prompts import get_system_prompt, list_available_sources

# List all available sources
sources = list_available_sources()
print(sources)

# Test a specific source
prompt = get_system_prompt('facebook')
print(prompt[:100])  # First 100 characters
```

## File Structure

```
Flask-Webhook-Server/
├── system_prompts.py          # System prompts configuration
├── chat_processor.py          # Updated to use dynamic prompts
├── webhook_handlers.py        # Updated to extract sourceforai
└── SYSTEM_PROMPTS_GUIDE.md   # This guide
```

## Support

For questions or issues with the system prompts feature:

1. Check the logs for sourceforai extraction
2. Verify webhook data structure
3. Test with the provided examples
4. Review the system_prompts.py configuration

The system is designed to be flexible and easy to extend, allowing you to create specialized AI personalities for each lead source.
