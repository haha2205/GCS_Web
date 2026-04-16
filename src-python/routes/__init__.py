from .config_routes import create_config_router
from .general_routes import create_general_router
from .operations_routes import create_operations_router

__all__ = [
    'create_config_router',
    'create_general_router',
    'create_operations_router',
]