import openai
import os
import logging
from typing import Dict, List

# Configure logging
logger = logging.getLogger(__name__)

# Get OpenAI configuration from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # Updated to gpt-4o-mini
OPENAI_SYSTEM_PROMPT = os.getenv('OPENAI_SYSTEM_PROMPT', """You are a friendly SMS assistant for FX Wells Gym. Keep replies under 2 sentences and be helpful and professional.""")

class OpenAIHandler:
    """
    Handles OpenAI API interactions for message processing using modern chat completions API
    """
    
    def __init__(self):
        self.model = OPENAI_MODEL
        # Use the newer OpenAI client syntax for version >=1.0.0
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
        
        if self.client:
            logger.info(f"OpenAI client initialized with model: {self.model}")
        else:
            logger.warning("OpenAI API key not configured. OpenAI functionality will be disabled.")
    
    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured"""
        return self.client is not None and OPENAI_API_KEY is not None
    
    def generate_chat_response(self, messages: List[Dict]) -> Dict:
        """
        Generate an AI response using proper OpenAI chat completions format
        messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
        """
        if not self.is_configured():
            return {
                'response': 'I apologize, but I am not configured to respond at the moment.',
                'error': 'OpenAI not configured'
            }
        
        try:
            logger.info(f"Generating chat response with model '{self.model}' using {len(messages)} messages")
            
            # Build API call parameters
            # GPT-5-mini and newer models require max_completion_tokens (not max_tokens)
            # and don't support custom temperature (uses default of 1)
            max_tokens = int(os.getenv('OPENAI_MAX_COMPLETION_TOKENS', '1000'))
            
            # Store parameter: Controls whether conversations are stored for training/logging
            # Set OPENAI_STORE_CONVERSATIONS=false to prevent storing (default: true)
            store_conversations = os.getenv('OPENAI_STORE_CONVERSATIONS', 'true').lower() == 'true'
            
            api_params = {
                'model': self.model,
                'messages': messages,
                'max_completion_tokens': max_tokens,  # Required for GPT-5-mini and newer models
                'store': store_conversations  # Store conversations for logging/training
            }
            
            logger.info(f"API call parameters: model={self.model}, max_completion_tokens={max_tokens}, store={store_conversations}")
            
            # Log full API call (excluding system prompt for readability)
            messages_for_log = []
            for msg in messages:
                if msg.get('role') == 'system':
                    messages_for_log.append({
                        'role': 'system',
                        'content': '[SYSTEM_PROMPT - excluded from log]'
                    })
                else:
                    messages_for_log.append(msg)
            logger.info(f"Full API call messages ({len(messages)} total): {messages_for_log}")
            
            response = self.client.chat.completions.create(**api_params)
            
            # Log full response
            logger.info(f"Full OpenAI API response:")
            logger.info(f"  - Request ID: {getattr(response, 'id', 'N/A')}")
            logger.info(f"  - Model: {getattr(response, 'model', 'N/A')}")
            logger.info(f"  - Choices count: {len(response.choices) if response.choices else 0}")
            if response.choices:
                for i, choice in enumerate(response.choices):
                    finish_reason = getattr(choice, 'finish_reason', 'N/A')
                    content = choice.message.content if choice.message else None
                    content_preview = content[:200] + "..." if content and len(content) > 200 else content
                    logger.info(f"  - Choice {i+1}: finish_reason={finish_reason}, content={repr(content_preview)}")
            if hasattr(response, 'usage') and response.usage:
                logger.info(f"  - Usage: prompt_tokens={response.usage.prompt_tokens}, completion_tokens={response.usage.completion_tokens}, total_tokens={response.usage.total_tokens}")
            
            # Log response ID for tracking in OpenAI dashboard
            if hasattr(response, 'id'):
                logger.info(f"OpenAI request ID: {response.id} (use this to find the request in your dashboard)")
            
            ai_response = response.choices[0].message.content
            
            if not ai_response:
                logger.warning("Received empty response from OpenAI")
                return {
                    'response': 'I apologize, but I received an empty response from the AI.',
                    'error': 'Empty response',
                    'model': self.model
                }
            
            logger.info(f"Generated AI response: {ai_response[:100]}...")
            
            return {
                'response': ai_response,
                'model': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'messages_sent': len(messages),
                'request_id': getattr(response, 'id', None)
            }
            
        except Exception as e:
            logger.error(f"Error generating chat response: {str(e)}")
            return {
                'response': 'I apologize, but I encountered an error while processing your message.',
                'error': str(e)
            }
    
    def generate_response(self, message: str, context: str = "") -> Dict:
        """
        Generate an AI response to a message using modern chat completions API
        This is the main function used for SMS responses (maintains backward compatibility)
        """
        if not self.is_configured():
            return {
                'response': 'I apologize, but I am not configured to respond at the moment.',
                'error': 'OpenAI not configured'
            }
        
        try:
            # Build messages array for chat completions
            messages = [
                {
                    "role": "system",
                    "content": "You are a friendly SMS assistant for FX Wells Gym. Keep replies under 2 sentences and be helpful and professional."
                }
            ]
            
            if context:
                messages.append({
                    "role": "system",
                    "content": f"Additional context: {context}"
                })
            
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Use the new chat completions method
            return self.generate_chat_response(messages)
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                'response': 'I apologize, but I encountered an error while processing your message.',
                'error': str(e)
            }

# Create a global instance
openai_handler = OpenAIHandler()
