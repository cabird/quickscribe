COSMOS_SYSTEM_FIELDS = {"_rid", "_self", "_etag", "_attachments", "_ts"}

def filter_cosmos_fields(document: dict) -> dict:
    """Removes Cosmos DB system fields from a document."""
    return {key: value for key, value in document.items() if key not in COSMOS_SYSTEM_FIELDS}
