import re
from typing import List, Dict, Any, Tuple
from fuzzywuzzy import fuzz


def validate_similarity(ocr_text: str, target_fields: List[str]) -> Tuple[float, Dict[str, Any]]:
    """
    Compares OCR text against a fixed set of 7 reference fields (e.g., brand, country).

    It calculates an average similarity score across contributing fields and provides
    a detailed dictionary of scores for each field, including special logic for
    Government warnings.

    Args:
        ocr_text: The raw OCR text to validate against.
        target_fields: A list containing exactly 7 target strings corresponding to the defined fields.

    Returns:
        A tuple consisting of (overall average score float, results dictionary).

    Raises:
        ValueError: If target_fields does not contain exactly 7 elements.
    """
    if len(target_fields) != 7:
        raise ValueError(f"Validation requires exactly 7 target fields, got {len(target_fields)}.")

    # Fixed keys defining the output structure and processing order
    field_keys = [
        "score_brand", "score_class", "score_abv",
        "score_contents", "score_address", "score_country",
        "score_govt"
    ]

    results: Dict[str, Any] = {}
    # Tracks scores that are non-zero and not marked as an NA override, for accurate average calculation.
    contributing_scores: List[float] = []
    
    # --- Fields 1 through 6: Standard Similarity Checks ---
    for i, key in enumerate(field_keys[:6]):
        target_text = target_fields[i].strip()
        score: int

        is_na_override = False

        if any(na_indicator.lower() in target_text.lower() for na_indicator in ["n/a", "na", "not applicable"]):
            # Handling of 'Not Applicable' fields results in a score of 0, but marks the field as NA
            score = 0
            is_na_override = True
        else:
            # Standard fuzzy token set ratio comparison (best for phrases/blocks of text)
            score = fuzz.token_set_ratio(ocr_text, target_text)
        
        results[key] = int(score)
        
        # Only contribute to the average score if a match was found AND it wasn't an NA override.
        if not is_na_override and score > 0:
             contributing_scores.append(float(score))


    # --- Field 7 (Government Warning): Enhanced Conditional Logic ---
    warning_target = target_fields[6].strip()
    const_warning_text = "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."
    
    GOV_TARGET_TOKENS = ["GOVERNMENT", "WARNING"]

    is_affirmative_trigger = any(t.lower() in warning_target.lower() for t in ["yes"])

    if is_affirmative_trigger:
        # Calculate score against the detailed government standard text
        score = fuzz.token_set_ratio(ocr_text, const_warning_text)
        results["score_govt"] = int(score)
        
        # Government warning always contributes if positive
        if score > 0:
             contributing_scores.append(float(score))

        # Calculate separate confidence based on identifying the key terms and case format
        caps_confidence = _get_caps_confidence(ocr_text, GOV_TARGET_TOKENS)
        results["is_caps_warning"] = caps_confidence
    else:
        # Logic for cases where the warning field is low relevance or does not contain a triggering word
        if "WARNING" not in warning_target.upper() and len(warning_target) < 10:
            # Case A: Original logic bypass (low relevance/short text)
            results["score_govt"] = None  # Explicitly set to None or handle missing key if preferred
            results["is_caps_warning"] = 5  # Default low confidence when check is bypassed
        else:
            # Case B: Fallback standard comparison
            score = fuzz.token_set_ratio(ocr_text, warning_target)
            results["score_govt"] = int(score)
            if score > 0: # Only contribute if the fallback score is positive
                contributing_scores.append(float(score))

            # Still calculate confidence even in the fallback path
            results["is_caps_warning"] = _get_caps_confidence(ocr_text, GOV_TARGET_TOKENS)

    # Calculate the overall average score across all eligible fields
    if contributing_scores:
        avg_score = sum(contributing_scores) / len(contributing_scores)
    else:
        # If no field contributed a positive score (e.g., all NA or empty input), default to 0.
        avg_score = 0.0
    
    return float(avg_score), results


def _get_caps_confidence(ocr_text: str, target_words: List[str], min_score: int = 85) -> int:
    """
    Calculates a confidence score (1-100) indicating how likely the OCR text contains
    the specified target words and if those words are written in all uppercase.

    The confidence is based on averaging individual word scores, which weigh
    fuzzy match strength and upper-case confirmation.

    Args:
        ocr_text: The raw optical character recognition text.
        target_words: A list of required keyword targets (e.g., ["GOVERNMENT", "WARNING"]).
        min_score: Minimum fuzzy ratio score needed for a word to contribute high confidence. Defaults to 85.

    Returns:
        An integer confidence score between 1 and 100, representing the average
        confidence across all target words.
    """
    # Extract only alpha-numeric tokens from the OCR text
    ocr_tokens = re.findall(r'\b\w+\b', ocr_text)
    per_word_scores: List[float] = []

    for target in target_words:
        target_clean = target.strip().upper()
        best_match = 0
        is_uppercase_confirmed = False

        for ocr_token in ocr_tokens:
            # Calculate fuzzy ratio between the clean target and the uppercase OCR token
            score = fuzz.ratio(target_clean, ocr_token.upper())
            if score > best_match:
                best_match = score
                # Check if the matched OCR token itself is strictly uppercase
                if len(ocr_token) > 0 and ocr_token == ocr_token.upper():
                    is_uppercase_confirmed = True

        # Calculate final confidence for this target word
        if best_match >= min_score:
            # High match score: weighted base score plus a bonus for confirmation of uppercase format
            base = int(best_match * 0.8)
            caps_bonus = 15 if is_uppercase_confirmed else 0
            word_score = min(100, max(1, base + caps_bonus))
        else:
            # Low match score: proportional to the fuzzy match ratio
            word_score = max(1, int(best_match * 0.3))

        per_word_scores.append(float(word_score))

    # Average confidence across all target words
    if not per_word_scores:
        return 5  # Default low score if no targets were processed
    
    avg_confidence = sum(per_word_scores) / len(per_word_scores)
    return max(1, min(100, int(round(avg_confidence))))