"""Compatibility shim for ChromaDB on Python 3.14+.

ChromaDB 1.5.x uses pydantic v1 BaseSettings which fails to infer types
for fields that have validators defined before the field declaration on
Python 3.14+. This module patches pydantic v1's type inference to fall
back to Any instead of raising ConfigError.

This module MUST be imported before chromadb to apply the patch.
"""

import sys
import warnings

if sys.version_info >= (3, 14):
    try:
        import pydantic.v1.fields as _pv1_fields
        from typing import Any

        _orig = _pv1_fields.ModelField._set_default_and_type

        def _patched_set_default_and_type(self):  # type: ignore[no-untyped-def]
            try:
                _orig(self)
            except Exception:
                self.outer_type_ = Any
                self.type_ = Any

        _pv1_fields.ModelField._set_default_and_type = _patched_set_default_and_type

        # Suppress the compatibility warning since we've patched it
        warnings.filterwarnings(
            "ignore",
            message="Core Pydantic V1 functionality",
            category=UserWarning,
        )
    except ImportError:
        pass  # pydantic v1 compat layer not present
