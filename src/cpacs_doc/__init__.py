"""Extractor for the CPACS documentation system.

Stage one of three (extractor, generator, viewer). Produces the intermediate
model and the build report; renders nothing.
"""

from .model import MODEL_VERSION

__all__ = ["MODEL_VERSION"]
