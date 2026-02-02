import openai
import os
import logging
from typing import Dict, List

# Configure logging
logger = logging.getLogger(__name__)

# Get OpenAI configuration from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # Default fallback, set OPENAI_MODEL env var for your model (e.g., 'gpt-5-mini')
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
            
            # Build API call parameters - GPT-5-mini and newer models require max_completion_tokens
            # and don't support custom temperature (uses default of 1)
            # Increased max_completion_tokens to prevent truncation issues
            max_tokens = int(os.getenv('OPENAI_MAX_COMPLETION_TOKENS', '1000'))
            api_params = {
                'model': self.model,
                'messages': messages,
                'max_completion_tokens': max_tokens  # Required for GPT-5-mini and newer models
            }
            
            logger.debug(f"API call parameters: model={self.model}, max_completion_tokens={max_tokens}")
            
            response = self.client.chat.completions.create(**api_params)
            
            # Log response structure for debugging
            logger.info(f"Response received - choices count: {len(response.choices) if response.choices else 0}")
            
            # Extract response content with better error handling
            if not response.choices or len(response.choices) == 0:
                logger.error("No choices in OpenAI response")
                logger.error(f"Full response object: {response}")
                return {
                    'response': 'I apologize, but I received an empty response from the AI.',
                    'error': 'No choices in response',
                    'model': self.model
                }
            
            choice = response.choices[0]
            finish_reason = getattr(choice, 'finish_reason', None)
            logger.info(f"Choice finish_reason: {finish_reason}")
            
            # Check if message exists
            if not choice.message:
                logger.error(f"No message in choice. Full choice: {choice}")
                return {
                    'response': 'I apologize, but I received an empty response from the AI.',
                    'error': 'No message in choice',
                    'finish_reason': finish_reason,
                    'model': self.model
                }
            
            ai_response = choice.message.content
            
            # Log raw content for debugging (before any processing)
            logger.info(f"Raw response content (length: {len(ai_response) if ai_response else 0}): {repr(ai_response[:200])}")
            
            # Check if content is None or empty
            if ai_response is None:
                logger.error(f"Response content is None. Finish reason: {finish_reason}")
                logger.error(f"Choice message object: {choice.message}")
                logger.error(f"Full choice object: {choice}")
                return {
                    'response': 'I apologize, but I received an empty response from the AI.',
                    'error': 'Response content is None',
                    'finish_reason': finish_reason,
                    'model': self.model
                }
            
            # Handle empty or whitespace-only content
            if not ai_response or not ai_response.strip():
                if finish_reason == 'length':
                    logger.warning(f"Response was truncated (finish_reason=length) but content is empty. This may indicate the token limit is too restrictive.")
                else:
                    logger.warning(f"Response content is empty string. Finish reason: {finish_reason}")
                return {
                    'response': 'I apologize, but I received an empty response from the AI.',
                    'error': 'Response content is empty',
                    'finish_reason': finish_reason,
                    'model': self.model
                }
            
            # Warn if response was truncated but still return it
            if finish_reason == 'length':
                logger.warning(f"Response was truncated due to max_completion_tokens limit. Consider increasing OPENAI_MAX_COMPLETION_TOKENS.")
            
            logger.info(f"Generated AI response: {ai_response[:100]}...")
            
            return {
                'response': ai_response,
                'model': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'messages_sent': len(messages),
                'finish_reason': getattr(choice, 'finish_reason', None)
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
