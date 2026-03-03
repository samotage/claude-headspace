"""Shared CLI utility functions.

Provides common helpers used across multiple CLI command groups
(channel_cli, msg_cli, persona_cli, etc.).
"""

import click


def print_table(headers: dict[str, str], rows: list[dict[str, str]]) -> None:
    """Print a formatted columnar table via click.echo.

    Args:
        headers: OrderedDict-style mapping of key -> display header.
        rows: List of dicts with the same keys as headers.
    """
    if not rows:
        return

    widths = {}
    for key, header in headers.items():
        widths[key] = max(
            len(header),
            max((len(r.get(key, "")) for r in rows), default=0),
        )

    header_line = "  ".join(h.ljust(widths[k]) for k, h in headers.items())
    click.echo(header_line)
    click.echo("  ".join("-" * widths[k] for k in headers))

    for row in rows:
        line = "  ".join(row.get(k, "").ljust(widths[k]) for k in headers)
        click.echo(line)
