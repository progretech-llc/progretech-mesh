"""Resolve installed factory helpers after the canonical ptinternal migration."""
from pathlib import Path


def factory_tool(home, name):
    if name not in {'factory-workday', 'factory-memory-activity'}:
        raise ValueError('unknown_factory_tool')
    canonical=Path(home)/'ptinternal/bin'/name
    legacy=Path(home)/'Rend/bin'/name
    return canonical if canonical.is_file() or not legacy.is_file() else legacy
