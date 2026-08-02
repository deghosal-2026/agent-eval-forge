"""Pack loading and validation.

Provides the :func:`load_pack` function for parsing and validating
scenario packs from YAML or JSON files against the EvalForge schema.
"""

from evalforge.loading.pack_loader import load_pack

__all__ = ["load_pack"]
