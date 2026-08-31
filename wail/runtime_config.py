_runtime_config = {
    "service": "default",
    "env": "default",
}

def configure(*, service=None, env=None):
    if service is not None:
        _runtime_config["service"] = service

    if env is not None:
        _runtime_config["env"] = env