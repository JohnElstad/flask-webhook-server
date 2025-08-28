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
        # Use only the modern OpenAI client
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
            logger.info(f"Generating chat response with {len(messages)} messages")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=100  # Reduced for shorter responses
            )
            
            ai_response = response.choices[0].message.content
            logger.info(f"Generated AI response: {ai_response}")
            
            return {
                'response': ai_response,
                'model': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'messages_sent': len(messages)
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
