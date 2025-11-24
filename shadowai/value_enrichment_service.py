"""Value enrichment service using OpenAI GPT-4o-mini.

This module provides functions to enrich AI usage events with business value
and governance context using LLM-based classification.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValueEnrichmentService:
    """Service for enriching events with business value insights using OpenAI."""

    SYSTEM_PROMPT = """You are classifying an AI usage event for an enterprise dataset.
Your job is to infer the business value and governance context of this single event.
You must return ONLY valid JSON matching the EXACT schema below.
Do not include any explanations, comments, or extra keys.

You will be given:
- Raw event metadata
- Any existing risk, PII, or policy flags
- A redacted summary or snippet of user content

Return JSON with EXACTLY these keys (no nesting):
{
  "value_category": "Productivity" | "Quality" | "Revenue" | "CostReduction" | "Innovation",
  "estimated_minutes_saved": <integer>,
  "business_outcome": "<what business result this enables>",
  "department": "<inferred department or 'Unknown'>",
  "risk_level": "Low" | "Medium" | "High",
  "policy_alignment": "Compliant" | "Questionable" | "Non-compliant",
  "summary": "<concise 1-2 sentence summary>"
}

If you are uncertain about something, choose the safest option (e.g., department = "Unknown")."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize the enrichment service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use (default: gpt-4o-mini)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.timeout = 30  # seconds

        # Check if openai package is available
        try:
            import openai
            self.openai = openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "openai package not found. Install it with: pip install openai"
            )

    def build_enrichment_payload(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Build the payload for LLM enrichment request.

        Args:
            event: Event dictionary from database

        Returns:
            Dictionary with event metadata for LLM processing
        """
        # Parse JSON fields if stored as strings
        risk_reasons = event.get('risk_reasons', '[]')
        if isinstance(risk_reasons, str):
            risk_reasons = json.loads(risk_reasons)

        pii_reasons = event.get('pii_reasons', '[]')
        if isinstance(pii_reasons, str):
            pii_reasons = json.loads(pii_reasons)

        # Build a sanitized input snippet (no actual content, just metadata)
        # In real implementation, you'd include sanitized/truncated prompts
        input_snippet = f"User accessed {event.get('provider', 'unknown')} AI service"

        # Determine action type from service
        service = event.get('service', 'unknown')
        action_type_map = {
            'chat': 'chat_completion',
            'code_assist': 'code_completion',
            'api': 'api_call',
            'web_ui': 'web_interaction'
        }
        action_type = action_type_map.get(service, 'other')

        payload = {
            "event_id": event.get('id'),
            "timestamp": event.get('timestamp'),
            "user_id": event.get('user_email', 'unknown'),
            "department_hint": event.get('department'),
            "tool": event.get('provider'),
            "model": event.get('service'),
            "action_type": action_type,
            "input_snippet": input_snippet,
            "existing_risk": {
                "risk_score": self._risk_level_to_score(event.get('risk_level')),
                "risk_level": event.get('risk_level', 'medium').upper(),
                "contains_pii": bool(event.get('pii_risk', 0)),
                "policy_flags": risk_reasons
            }
        }

        return payload

    def _risk_level_to_score(self, risk_level: str) -> int:
        """Convert risk level string to numeric score.

        Args:
            risk_level: Risk level (low/medium/high)

        Returns:
            Numeric score 0-100
        """
        mapping = {
            'low': 20,
            'medium': 50,
            'high': 80
        }
        return mapping.get(str(risk_level).lower(), 50)

    def call_llm_for_enrichment(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """Call OpenAI API to enrich event data.

        Args:
            payload: Event payload for enrichment

        Returns:
            Tuple of (parsed_enrichment, raw_response, error_message)
        """
        user_content = json.dumps(payload, indent=2)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Calling OpenAI API (attempt {attempt + 1}/{self.max_retries})...")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=500,
                    timeout=self.timeout
                )

                raw_response = response.choices[0].message.content
                logger.debug(f"Raw LLM response: {raw_response}")

                # Parse JSON response
                try:
                    enrichment = json.loads(raw_response)

                    # Validate required fields
                    required_fields = [
                        'value_category',
                        'estimated_minutes_saved',
                        'business_outcome',
                        'department',
                        'risk_level',
                        'policy_alignment',
                        'summary'
                    ]

                    missing_fields = [f for f in required_fields if f not in enrichment]
                    if missing_fields:
                        error = f"Missing required fields: {', '.join(missing_fields)}"
                        logger.warning(error)
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (2 ** attempt))
                            continue
                        return None, raw_response, error

                    logger.info("Successfully enriched event")
                    return enrichment, raw_response, None

                except json.JSONDecodeError as e:
                    error = f"Failed to parse JSON response: {e}"
                    logger.warning(error)
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    return None, raw_response, error

            except self.openai.APITimeoutError as e:
                error = f"OpenAI API timeout: {e}"
                logger.warning(error)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                return None, None, error

            except self.openai.RateLimitError as e:
                error = f"OpenAI rate limit exceeded: {e}"
                logger.warning(error)
                # Wait longer for rate limits
                time.sleep(self.retry_delay * (2 ** (attempt + 2)))
                if attempt < self.max_retries - 1:
                    continue
                return None, None, error

            except self.openai.APIError as e:
                error = f"OpenAI API error: {e}"
                logger.error(error)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                return None, None, error

            except Exception as e:
                error = f"Unexpected error: {e}"
                logger.error(error, exc_info=True)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                return None, None, error

        return None, None, "Max retries exceeded"

    def enrich_event(
        self,
        event: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """Enrich a single event with business value insights.

        Args:
            event: Event dictionary from database

        Returns:
            Tuple of (enrichment, raw_response, error)
        """
        try:
            # Build payload
            payload = self.build_enrichment_payload(event)

            # Call LLM
            enrichment, raw_response, error = self.call_llm_for_enrichment(payload)

            return enrichment, raw_response, error

        except Exception as e:
            error = f"Failed to enrich event: {e}"
            logger.error(error, exc_info=True)
            return None, None, error


def create_enrichment_service() -> ValueEnrichmentService:
    """Factory function to create enrichment service instance.

    Returns:
        ValueEnrichmentService instance

    Raises:
        ValueError: If API key is not configured
    """
    return ValueEnrichmentService()
