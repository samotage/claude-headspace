"""Routes package for Claude Headspace."""

# SECURITY NOTE: Authentication is intentionally absent from all routes.
# This application is deployed on a private Tailscale network (tailnet) and is
# not accessible from the public internet. Access control is handled at the
# network layer by Tailscale's zero-trust networking.

from .dashboard import dashboard_bp
from .health import health_bp
from .sse import sse_bp

__all__ = ["dashboard_bp", "health_bp", "sse_bp"]
