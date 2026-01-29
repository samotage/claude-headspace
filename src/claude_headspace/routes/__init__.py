"""Routes package for Claude Headspace."""

from .dashboard import dashboard_bp
from .health import health_bp
from .sse import sse_bp

__all__ = ["dashboard_bp", "health_bp", "sse_bp"]
