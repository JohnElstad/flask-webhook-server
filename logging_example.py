#!/usr/bin/env python3
"""
Example script showing how to use the new Supabase logging system
"""

import os
import logging
from dotenv import load_dotenv
from supabase_logger import (
    setup_supabase_logging,
    info_with_context,
    error_with_context,
    warning_with_context,
    debug_with_context
)

# Load environment variables
load_dotenv()

def main():
    """Example of using the new logging system"""
    
    # Set up logging (this will be done automatically in your main server)
    setup_supabase_logging(
        table_name='server_logs',
        log_level=logging.INFO,
        include_console=True
    )
    
    print("Testing Supabase logging system...")
    
    # Example 1: Basic logging
    info_with_context("Server started successfully")
    
    # Example 2: Logging with contact context
    contact_id = "test_contact_123"
    info_with_context(
        "Processing webhook for contact",
        contact_id=contact_id,
        webhook_type="contact.reply",
        operation="webhook_processing"
    )
    
    # Example 3: Logging errors with context
    try:
        # Simulate an error
        raise ValueError("Test error for logging")
    except Exception as e:
        error_with_context(
            f"Error processing webhook: {str(e)}",
            contact_id=contact_id,
            webhook_type="contact.reply",
            operation="webhook_processing",
            exc_info=True
        )
    
    # Example 4: Warning with context
    warning_with_context(
        "Rate limit approaching for contact",
        contact_id=contact_id,
        operation="rate_limit_check"
    )
    
    # Example 5: Debug logging (only if log level is DEBUG)
    debug_with_context(
        "Detailed processing information",
        contact_id=contact_id,
        operation="debug_info"
    )
    
    print("Logging examples completed. Check your Supabase server_logs table!")

if __name__ == "__main__":
    main()
