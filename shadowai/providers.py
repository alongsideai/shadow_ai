"""Provider and service detection from URLs and hostnames."""

from urllib.parse import urlparse
from typing import Tuple
from .models import Provider, Service


def detect_provider_and_service(url: str) -> Tuple[str, str]:
    """
    Detect the AI provider and service type from a URL.

    Args:
        url: The URL to analyze

    Returns:
        Tuple of (provider, service) as strings
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path.lower()

    # OpenAI detection
    if "openai.com" in hostname:
        if "api.openai.com" in hostname:
            if "/v1/chat" in path or "/chat/completions" in path:
                return Provider.OPENAI.value, Service.CHAT.value
            elif "/v1/embeddings" in path:
                return Provider.OPENAI.value, Service.EMBEDDINGS.value
            else:
                return Provider.OPENAI.value, Service.API.value
        elif "chat.openai.com" in hostname:
            return Provider.OPENAI.value, Service.WEB_UI.value
        else:
            return Provider.OPENAI.value, Service.UNKNOWN.value

    # Anthropic detection
    if "anthropic.com" in hostname:
        if "api.anthropic.com" in hostname:
            if "/v1/messages" in path:
                return Provider.ANTHROPIC.value, Service.CHAT.value
            else:
                return Provider.ANTHROPIC.value, Service.API.value
        elif "claude.ai" in hostname or "console.anthropic.com" in hostname:
            return Provider.ANTHROPIC.value, Service.WEB_UI.value
        else:
            return Provider.ANTHROPIC.value, Service.UNKNOWN.value

    # Claude.ai (standalone)
    if "claude.ai" in hostname:
        return Provider.ANTHROPIC.value, Service.WEB_UI.value

    # Google/Gemini detection
    if "generativelanguage.googleapis.com" in hostname or "gemini" in hostname.lower():
        if "/v1/models" in path or "/generateContent" in path:
            return Provider.GOOGLE.value, Service.CHAT.value
        else:
            return Provider.GOOGLE.value, Service.API.value

    # GitHub Copilot detection
    if "githubcopilot.com" in hostname or "copilot" in hostname.lower():
        return Provider.GITHUB_COPILOT.value, Service.CODE_ASSIST.value

    # Perplexity detection
    if "perplexity.ai" in hostname:
        return Provider.PERPLEXITY.value, Service.WEB_UI.value

    # Unknown AI provider heuristic - check if "ai" is in the hostname
    if "ai" in hostname.lower() or "gpt" in hostname.lower() or "llm" in hostname.lower():
        return Provider.UNKNOWN.value, Service.UNKNOWN.value

    # If we get here, it's not a recognized AI provider
    return Provider.UNKNOWN.value, Service.UNKNOWN.value


def is_ai_related(url: str) -> bool:
    """
    Check if a URL appears to be AI-related.

    Args:
        url: The URL to check

    Returns:
        True if the URL appears to be AI-related
    """
    provider, _ = detect_provider_and_service(url)
    return provider != Provider.UNKNOWN.value or _looks_like_ai_url(url)


def _looks_like_ai_url(url: str) -> bool:
    """Heuristic check if URL looks AI-related."""
    url_lower = url.lower()
    ai_keywords = ["ai", "gpt", "llm", "chat", "copilot", "assistant", "gemini", "claude", "openai", "anthropic"]
    return any(keyword in url_lower for keyword in ai_keywords)
