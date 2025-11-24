"""Use-case classification for Shadow AI Detection Platform."""

from typing import List
from .models import AIUsageEvent, Provider, Service


# Threshold for data extraction classification
DATA_EXTRACTION_THRESHOLD = 10_000  # bytes


def infer_use_case(event: AIUsageEvent) -> str:
    """
    Infer the high-level use case for an AI usage event.

    Categories:
    - "content_generation": Creating content, documents, writing assistance
    - "code_assistance": Programming help, code completion
    - "data_extraction": Uploading documents/records for analysis
    - "analysis_or_chat": Q&A, analysis, general chat
    - "unknown": Cannot determine

    Args:
        event: AIUsageEvent to classify

    Returns:
        Use case string
    """
    provider = event.provider
    service = event.service
    bytes_sent = event.bytes_sent or 0

    # Rule 1: GitHub Copilot is always code assistance
    if provider == Provider.GITHUB_COPILOT.value:
        return "code_assistance"

    # Rule 2: Web UI usage typically indicates content generation
    if service == Service.WEB_UI.value and provider in {
        Provider.OPENAI.value,
        Provider.ANTHROPIC.value,
        Provider.GOOGLE.value
    }:
        return "content_generation"

    # Rule 3: Large payloads to chat services suggest data extraction
    if service == Service.CHAT.value and bytes_sent >= DATA_EXTRACTION_THRESHOLD:
        return "data_extraction"

    # Rule 4: Chat services with normal payloads are analysis/Q&A
    if service == Service.CHAT.value:
        return "analysis_or_chat"

    # Rule 5: API endpoints with large payloads
    if service == Service.API.value and bytes_sent >= DATA_EXTRACTION_THRESHOLD:
        return "data_extraction"

    # Rule 6: Embeddings service typically for document processing
    if service == Service.EMBEDDINGS.value:
        return "data_extraction"

    # Default: unknown
    return "unknown"


def apply_use_case_classification(events: List[AIUsageEvent]) -> None:
    """
    Apply use-case classification to a list of events in-place.

    Args:
        events: List of AIUsageEvent objects to classify
    """
    for event in events:
        event.use_case = infer_use_case(event)


def get_use_case_display_name(use_case: str) -> str:
    """
    Get business-friendly display name for a use case.

    Args:
        use_case: Use case code

    Returns:
        Human-readable display name
    """
    display_names = {
        "content_generation": "Content Generation",
        "code_assistance": "Code Assistance",
        "data_extraction": "Data Extraction (Docs/Records)",
        "analysis_or_chat": "Analysis / Q&A",
        "unknown": "Unknown"
    }

    return display_names.get(use_case, use_case.title())


def get_use_case_description(use_case: str) -> str:
    """
    Get detailed description for a use case.

    Args:
        use_case: Use case code

    Returns:
        Detailed description
    """
    descriptions = {
        "content_generation": "Creating or editing content through web interfaces, including documents, emails, presentations, and creative writing.",
        "code_assistance": "Programming support including code completion, debugging, refactoring, and technical documentation.",
        "data_extraction": "Uploading documents, records, or large data sets for analysis, summarization, or extraction of insights.",
        "analysis_or_chat": "Question-answering, general analysis, research, and conversational interactions with AI assistants.",
        "unknown": "Usage pattern does not match known categories or insufficient data to classify."
    }

    return descriptions.get(use_case, "No description available.")
