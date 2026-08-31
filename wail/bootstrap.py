import sys
import pkgutil
import importlib


def bootstrap_import_alias():
    try:
        import wail_private
    except ImportError:
        return

    from wail_private.native_integrity import verify_native_runtime

    verify_native_runtime()

    prefix_private = "wail_private"
    prefix_public = "wail.runtime"

    for _, module_name, _ in pkgutil.walk_packages(
        wail_private.__path__, prefix_private + "."
    ):
        public_name = module_name.replace(prefix_private, prefix_public, 1)

        try:
            module = importlib.import_module(module_name)
            sys.modules[public_name] = module
        except Exception:
            pass