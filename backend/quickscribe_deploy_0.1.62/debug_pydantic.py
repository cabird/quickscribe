"""
Debug utility for tracking Pydantic serialization issues
"""

import warnings
import traceback
import logging

def warning_capture(message, category, filename, lineno, file=None, line=None):
    """
    Custom warning handler that logs the full stack trace
    """
    logging.error(f"WARNING: {category.__name__}: {message}")
    logging.error(f"From {filename}:{lineno}")
    
    # Log the stack trace
    stack = traceback.extract_stack()
    stack_trace = "\n".join([f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in stack[:-1]])
    logging.error(f"Stack trace:\n{stack_trace}")
    
    # Call the original handler
    return warnings.showwarning(message, category, filename, lineno, file, line)

def setup_warning_capture():
    """Enable detailed warning capture"""
    original_showwarning = warnings.showwarning
    warnings.showwarning = warning_capture
    return original_showwarning

def restore_warning_handler(original_handler):
    """Restore original warning handler"""
    warnings.showwarning = original_handler
