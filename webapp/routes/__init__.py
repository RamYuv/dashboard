from .blueprint import main_bp
from . import admin  # noqa: F401
from . import api  # noqa: F401
from . import auth  # noqa: F401
from . import dashboard  # noqa: F401
from . import misc  # noqa: F401

__all__ = ["main_bp"]
