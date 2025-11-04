"""
Helper utilities for Cosmos DB handlers
"""
import re


def slugify(text: str) -> str:
    """Convert text to a slug suitable for tag IDs and other URL-safe identifiers."""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    # Remove leading/trailing hyphens
    return text.strip('-')
