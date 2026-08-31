import json
import os
import hmac
import hashlib
import threading
import time
from .logger import logger
from wail.runtime.version import ENGINE_VERSION, SCHEMA_VERSION

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from pathlib import Path

GLOBAL_RUNTIME_CACHE = {}

BASE_DIR = Path(__file__).resolve().parent.parent.parent

STATE_DIR = BASE_DIR / "wail_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = STATE_DIR / "wail_state.json"
LOCK_FILE = STATE_DIR / "wail_state.json.lock"

_SECRET = os.getenv("WAIL_STATE_SECRET")

if _SECRET:
    SECRET_KEY = _SECRET.encode()
else:
    SECRET_KEY = None


class StateCorruptionError(Exception):
    pass


class StateStore:
    __slots__ = (
        "is_leader",
        "_dirty",
        "_state",
        "_lock",
        "_thread",
        "_running",
        "_lock_handle",
        "_runtime_cache",
        "_model_state",
    )

    def __init__(self):
        self.is_leader = False
        self._dirty = False
        self._state = None
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._lock_handle = None
        self._runtime_cache = GLOBAL_RUNTIME_CACHE
        self._model_state = {}

    def start(self):

        if self._running:
            return

        try:
            self._lock_handle = open(LOCK_FILE, "w")

            if os.name == "nt":
                msvcrt.locking(
                    self._lock_handle.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )
            else:
                fcntl.flock(
                    self._lock_handle,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )

            self.is_leader = True

        except Exception as e:
            raise RuntimeError(f"[WAIL] State leader lock failed: {e}")

        self._running = True
        self._thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
        )
        self._thread.start()

    def _sign(self, data: bytes) -> str:
        if not SECRET_KEY:
            return None
        return hmac.new(
            SECRET_KEY,
            data,
            hashlib.sha256,
        ).hexdigest()

    def _verify(self, data: bytes, signature: str) -> bool:
        if not SECRET_KEY:
            return False

        expected = self._sign(data)
        return hmac.compare_digest(expected, signature)

    def mark_dirty(self, state):

        if not self.is_leader:
            raise RuntimeError("[WAIL] State leader not acquired. Execution blocked.")

        with self._lock:
            self._state = state
            self._dirty = True

    def flush_sync(self):
        if not self.is_leader:
            raise RuntimeError("[WAIL] State leader not acquired. Execution blocked.")
        self._flush_now()

    def _flush_loop(self):
        while self._running:
            time.sleep(1)

            try:
                self._flush_now()
            except Exception as e:
                logger.error(f"STATE STORE: background flush failed: {e}")

    def _flush_now(self):

        with self._lock:

            if not self._dirty:
                return

            state = self._state

            try:
                payload_bytes = json.dumps(
                    state,
                    sort_keys=True,
                ).encode()

                signature = self._sign(payload_bytes)

                wrapper = {
                    "signature": signature,
                    "payload": state,
                }

                tmp_file = Path(str(STATE_FILE) + ".tmp")

                with open(tmp_file, "w") as f:
                    json.dump(wrapper, f)
                    f.flush()
                    os.fsync(f.fileno())
                    
                last_error = None

                for attempt in range(3):
                    try:
                        os.replace(tmp_file, STATE_FILE)
                        last_error = None
                        break

                    except PermissionError as e:
                        last_error = e

                        if os.name != "nt":
                            raise

                        if attempt < 2:
                            time.sleep(0.05)

                if last_error is not None:
                    raise last_error


                self._dirty = False
                logger.debug("STATE STORE: flush success")

            except Exception as e:
                self._dirty = True
                raise RuntimeError(f"[WAIL] STATE FLUSH ERROR: {e}")


    def load(self):
        if not os.path.exists(STATE_FILE):

            initial_state = {"invocation_count": 0, "security_violation": False}

            try:
                payload_bytes = json.dumps(initial_state, sort_keys=True).encode()

                if SECRET_KEY:
                    signature = self._sign(payload_bytes)
                else:
                    signature = "no-signature"

                wrapper = {
                    "signature": signature,
                    "payload": initial_state,
                }

            except Exception:
                pass

            return initial_state

        try:
            with open(STATE_FILE, "r") as f:
                wrapper = json.load(f)

            signature = wrapper.get("signature")
            payload = wrapper.get("payload")

            if payload is None:
                raise StateCorruptionError("Missing payload")

            if not isinstance(payload, dict):
                raise StateCorruptionError("Invalid payload")

            raw = json.dumps(
                payload,
                sort_keys=True,
            ).encode()

            if SECRET_KEY:
                if signature is None:
                    raise StateCorruptionError("Missing signature")

                if not self._verify(raw, signature):
                    raise StateCorruptionError("Signature mismatch")

            if payload.get("security_violation"):
                raise RuntimeError(
                    "[WAIL] Security violation detected. Execution blocked."
                )

            return payload

        except Exception as e:
            corrupt_name = STATE_DIR / f"wail_state.json.corrupt.{int(time.time())}"

            try:
                os.rename(STATE_FILE, corrupt_name)
            except Exception:
                pass

            raise RuntimeError("[WAIL] State corruption detected. Execution blocked.")


_state_store_instance = None

def get_state_store():
    global _state_store_instance

    if _state_store_instance is None:
        _state_store_instance = StateStore()

    return _state_store_instance

state_store = get_state_store()

def persist_runtime_state():
    from wail_private.runtime_policy import runtime_policy

    state_store.mark_dirty(
        {
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "policy_version": runtime_policy.get().version,
            "policy": runtime_policy.export(),
            "runtime_cache": GLOBAL_RUNTIME_CACHE,
        }
    )

def enforce_state():
    try:
        if not state_store.is_leader:
            return False

        state = state_store.load()
        if not state:
            return False

        return True

    except Exception as e:
        return False
