"""Consistent errors for explicitly requested optional features."""

from importlib import import_module
from types import ModuleType


class OptionalDependencyError(ImportError):
    """An optional feature dependency is absent from the installation."""


def require_dependency(module: str, extra: str) -> ModuleType:
    try:
        return import_module(module)
    except ImportError as error:
        if module == "torch" and extra != "build":
            message = (
                "Local translation requires PyTorch, which is installed separately. "
                "For CPU: python -m pip install torch --index-url https://download.pytorch.org/whl/cpu. "
                "For CUDA, choose a compatible build at https://pytorch.org/get-started/locally/."
            )
        elif module == "cupy":
            message = (
                "spaCy GPU inference requires CuPy, which is installed separately. "
                'For CUDA 12: python -m pip install "cupy-cuda12x[ctk]". '
                'For CUDA 13: python -m pip install "cupy-cuda13x[ctk]". '
                "Install only one variant and use a compatible NVIDIA driver. "
                "See https://docs.cupy.dev/en/stable/install.html."
            )
        else:
            message = (
                f"Optional dependency {module!r} is unavailable; install gdelt-regkg[{extra}]."
            )
        raise OptionalDependencyError(message) from error
