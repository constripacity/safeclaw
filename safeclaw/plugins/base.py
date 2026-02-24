"""Plugin interface definition.

Every SafeClaw plugin is a module that exposes a ``run`` function with the
following signature::

    def run(policy: Policy, target: Path) -> tuple[str, list[str]]:
        '''Execute the plugin.

        Args:
            policy: The active security policy (use for limits, root path, etc.).
            target: The file or directory to operate on.

        Returns:
            A tuple of (human-readable message, list of touched file paths).
        '''
        ...

To register a new plugin:

1. Create a module in ``safeclaw/plugins/`` with a ``run`` function.
2. Add the plugin name (module filename without ``.py``) to the registry
   in ``safeclaw/runner.py`` inside ``_register_builtins()``.
3. Add the plugin name to ``allowed_plugins`` in ``policy.yaml``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from safeclaw.policy import Policy


class PluginProtocol(Protocol):
    """Structural type that all plugins must satisfy."""

    def __call__(self, policy: Policy, target: Path) -> tuple[str, list[str]]: ...
