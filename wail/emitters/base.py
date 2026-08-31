class BaseEmitter:

    def emit(self, trace: dict):
        raise NotImplementedError

    def flush(self):
        return None

    def shutdown(self):
        return None

    def health(self) -> dict:
        return {"status": "unknown"}
