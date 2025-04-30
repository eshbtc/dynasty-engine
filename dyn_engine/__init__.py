"""Dynasty Engine package (Phase-0 scaffolding).

Re-exports legacy top-level modules so existing imports continue to work while we
incrementally migrate to a proper package layout.
"""
from importlib import import_module
import sys as _sys

_legacy_modules = [
    "agentic_core",
    "order_helper",
    "auto_hedger",
    "multi_asset_manager",
    "db_manager",
    "data_provider",
    "kelly",
]

for _name in _legacy_modules:
    try:
        _mod = import_module(_name)
        _sys.modules[f"dyn_engine.{_name}"] = _mod  # alias under new package
        globals()[_name] = _mod
    except ModuleNotFoundError:
        pass  # will be added later or is optional

__all__ = _legacy_modules
