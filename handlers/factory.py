from .chdv5 import ChdV5Handler
from .rvz import RvzHandler
from .xbox_patch import XboxPatchHandler
from .squashfs import SquashFSHandler

def create_handler(handler_type: str, tools_path, log_callback, progress_callback):
    handlers = {
        "chd_v5": ChdV5Handler,
        "rvz": RvzHandler,
        "xbox_patch": XboxPatchHandler,
        "squashfs": SquashFSHandler
    }
    if handler_type not in handlers:
        raise ValueError(f"Handler type '{handler_type}' not supported")
    return handlers[handler_type](tools_path, log_callback, progress_callback)
