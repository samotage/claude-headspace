"""Voice matching logic — fuzzy match and picker option matching. No Flask, no DB."""

import logging
import re

logger = logging.getLogger(__name__)


def _fuzzy_match(ref_text: str, items: list, get_names: callable) -> dict:
    """Fuzzy match a reference string against a list of items.

    Shared matching logic used by both channel and persona matchers.

    Args:
        ref_text: The user's voice reference text
        items: List of objects to match against
        get_names: Callable(item) -> list[str] returning lowercase name
            variants to match (e.g. [name, slug])

    Returns:
        {"match": item, "confidence": float} for single match
        {"ambiguous": [item, ...]} for multiple matches
        {"no_match": True} for no matches
    """
    ref = ref_text.strip().lower()
    ref = re.sub(r"^(the|a|an)\s+", "", ref)
    ref = ref.rstrip("?!.")

    candidates = []
    for item in items:
        names = get_names(item)

        # 1. Exact match on any name variant
        if ref in names:
            return {"match": item, "confidence": 1.0}

        # 2. Substring match
        matched_substring = False
        for n in names:
            if ref in n or n in ref:
                candidates.append((item, 0.8))
                matched_substring = True
                break
        if matched_substring:
            continue

        # 3. Token overlap
        ref_tokens = set(ref.split())
        all_tokens = set()
        for n in names:
            all_tokens |= set(n.replace("-", " ").split())

        overlap = ref_tokens & all_tokens
        if overlap and len(overlap) >= len(ref_tokens) * 0.5:
            score = len(overlap) / max(len(ref_tokens), len(all_tokens))
            candidates.append((item, score))

    if not candidates:
        return {"no_match": True}

    candidates.sort(key=lambda x: x[1], reverse=True)

    if len(candidates) == 1:
        return {"match": candidates[0][0], "confidence": candidates[0][1]}

    if candidates[0][1] - candidates[1][1] > 0.2:
        return {"match": candidates[0][0], "confidence": candidates[0][1]}

    ambiguous = [c[0] for c in candidates if c[1] >= candidates[0][1] - 0.1]
    return {"ambiguous": ambiguous}


def _match_channel(channel_ref: str, channels: list) -> dict:
    """Fuzzy match a channel reference against active channels."""
    return _fuzzy_match(
        channel_ref,
        channels,
        lambda ch: [ch.name.lower(), ch.slug.lower()],
    )


# Affirmative patterns for matching voice text to "Yes" options
_AFFIRMATIVE_PATTERNS = {
    "yes",
    "yeah",
    "yep",
    "yup",
    "sure",
    "ok",
    "okay",
    "approve",
    "go",
    "proceed",
    "do it",
    "go ahead",
    "absolutely",
    "confirmed",
    "confirm",
}


def _match_picker_option(text: str, labels: list[str]) -> int:
    """Match voice text to the best picker option by label.

    Used for TUI pickers that don't have an "Other" option (e.g., ExitPlanMode).
    Tries exact match first, then fuzzy/semantic matching.

    Args:
        text: The user's voice text (e.g., "Yes", "go ahead", "no")
        labels: The option labels in order (e.g., ["Yes", "No"])

    Returns:
        Index of the best matching option (0-based). Defaults to 0 (first option)
        if no confident match is found — safer to approve than to reject for plan
        approval where the user explicitly initiated the response.
    """
    normalized = text.strip().lower()

    # Exact match (case-insensitive)
    for i, label in enumerate(labels):
        if normalized == label.lower():
            return i

    # Substring match — user text contains an option label
    for i, label in enumerate(labels):
        if label.lower() in normalized:
            return i

    # Semantic match — check negation FIRST so "don't do it" doesn't match
    # the affirmative "do it" pattern.
    words = set(normalized.split())
    _negative_words = {"no", "nope", "nah", "reject", "stop", "cancel"}
    if words & _negative_words or "don't" in normalized or "not" in words:
        for i, label in enumerate(labels):
            if label.lower() in ("no", "reject", "cancel"):
                return i
        return min(1, len(labels) - 1)  # Default to second option for negative

    # Affirmative patterns (after negation check to prevent "don't do it" → "do it")
    # Use word-boundary matching to avoid false positives (e.g., "cargo" matching "go")
    if words & _AFFIRMATIVE_PATTERNS or any(
        p in normalized for p in _AFFIRMATIVE_PATTERNS if " " in p
    ):
        for i, label in enumerate(labels):
            if label.lower() in ("yes", "approve", "ok", "proceed"):
                return i
        return 0  # Default to first option for affirmative

    # No confident match — default to first option (typically "Yes"/approve).
    # The user explicitly sent a response to an AWAITING_INPUT agent, so they
    # almost certainly intended to approve rather than reject.
    logger.warning(
        f"No confident match for '{text}' against options {labels}, "
        f"defaulting to index 0 ({labels[0] if labels else '?'})"
    )
    return 0
