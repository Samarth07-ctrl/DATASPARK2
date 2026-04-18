# ==============================================================================
# File: backend/services/pii_masking.py
# ==============================================================================
# PURPOSE: PII Masking Service using Microsoft Presidio
#
# WHY THIS MATTERS (Enterprise Compliance):
# When we send data samples to the Gemini API for analysis, we are potentially
# leaking PII (Social Security Numbers, emails, phone numbers, credit cards)
# to a third-party API. In regulated industries (HIPAA, GDPR, SOC2), this is
# a compliance violation that can result in fines.
#
# This module scans and redacts PII from data samples BEFORE they leave our
# backend, ensuring that only anonymized placeholders reach the Gemini API.
#
# ARCHITECTURE:
#   _build_column_profile_polars()  -->  pii_service.mask_data_samples()  -->  Gemini API
#                                        ^^ sanitizes samples here ^^
# ==============================================================================

import logging
from typing import List, Dict, Optional

logger = logging.getLogger("dataspark.pii")

# Lazy-load Presidio to avoid slow startup when PII masking is disabled
_analyzer = None
_anonymizer = None
_PRESIDIO_AVAILABLE = None


def _ensure_presidio():
    """Lazy-initialize Presidio engine. Only loads spacy model on first use."""
    global _analyzer, _anonymizer, _PRESIDIO_AVAILABLE

    if _PRESIDIO_AVAILABLE is not None:
        return _PRESIDIO_AVAILABLE

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _PRESIDIO_AVAILABLE = True
        logger.info("Presidio PII masking engine initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Presidio could not be initialized: {e}. PII masking disabled.")
        _PRESIDIO_AVAILABLE = False
        return False


# PII entity types we scan for
DEFAULT_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "LOCATION",
]


def mask_text(text: str, entities: Optional[List[str]] = None, score_threshold: float = 0.4) -> str:
    """
    Scans a single text string for PII and replaces detected entities with
    type-based placeholders like <EMAIL_ADDRESS>, <PHONE_NUMBER>, etc.

    Args:
        text: The raw text to scan.
        entities: List of entity types to detect. Defaults to DEFAULT_ENTITIES.
        score_threshold: Minimum confidence score to consider a detection valid.

    Returns:
        The anonymized text with PII replaced by placeholders.
    """
    if not _ensure_presidio():
        return text  # Return unmasked if Presidio is unavailable

    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return text

    scan_entities = entities or DEFAULT_ENTITIES

    try:
        results = _analyzer.analyze(
            text=text,
            entities=scan_entities,
            language="en",
            score_threshold=score_threshold,
        )

        if not results:
            return text

        anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text

    except Exception as e:
        logger.warning(f"PII masking failed for text sample: {e}")
        return text  # Return original on error — fail open


def mask_data_samples(samples: List[str]) -> List[str]:
    """
    Masks PII in a list of data sample strings.
    This is the primary entry point — called before sending column samples to Gemini.

    Args:
        samples: List of string values from a data column.

    Returns:
        List of anonymized strings with PII redacted.
    """
    if not _ensure_presidio():
        return samples

    return [mask_text(s) for s in samples]


def mask_column_profiles(profiles: List[Dict]) -> List[Dict]:
    """
    Higher-level function: masks the 'data_sample' field in each column profile
    dictionary before it's sent to the Gemini API.

    This is the function called in the analysis pipeline:
        profiles = [_build_column_profile_polars(df, col) for col in df.columns]
        masked_profiles = mask_column_profiles(profiles)
        ai_results = await call_gemini_batch_analysis(masked_profiles)

    Returns:
        New list of profile dicts with masked data_sample values.
    """
    if not _ensure_presidio():
        return profiles

    masked = []
    total_redactions = 0

    for profile in profiles:
        new_profile = profile.copy()
        samples = new_profile.get('data_sample', [])

        if samples:
            masked_samples = mask_data_samples(samples)
            # Count how many samples were actually changed
            redactions = sum(1 for orig, masked in zip(samples, masked_samples) if orig != masked)
            total_redactions += redactions
            new_profile['data_sample'] = masked_samples

        masked.append(new_profile)

    if total_redactions > 0:
        logger.info(f"PII masking: Redacted {total_redactions} sample values across {len(profiles)} columns.")

    return masked


def get_pii_status() -> Dict:
    """Returns the current status of the PII masking engine. Used by /health endpoint."""
    available = _ensure_presidio()
    return {
        "enabled": available,
        "entities_scanned": DEFAULT_ENTITIES if available else [],
        "engine": "Microsoft Presidio" if available else "Not available"
    }
