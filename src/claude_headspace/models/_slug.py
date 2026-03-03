"""Shared slug utilities for models with auto-generated slugs.

Used by Channel and Persona models that share the same slug generation pattern:
a temporary slug on insert, replaced by the real slug via an after_insert event.
"""

import re
from uuid import uuid4


def temp_slug() -> str:
    """Generate a temporary slug for initial insert (replaced by after_insert event)."""
    return f"_pending_{uuid4().hex[:12]}"


def slugify(text: str) -> str:
    """Sanitize text for use in a slug: lowercase, replace spaces/special chars with hyphens."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)  # Replace non-alphanumeric with hyphens
    s = re.sub(r"-+", "-", s)            # Collapse consecutive hyphens
    return s.strip("-")                   # Remove leading/trailing hyphens
