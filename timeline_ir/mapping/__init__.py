"""Current device mapping implementation for the Timeline IR pipeline."""

from .adapter import to_pipeline_contract
from .resolver import resolve

__all__ = ["resolve", "to_pipeline_contract"]
