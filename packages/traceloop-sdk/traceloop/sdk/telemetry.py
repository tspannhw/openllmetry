import os
import uuid
from pathlib import Path
import logging
import sys
from posthog import Posthog
import sentry_sdk
from traceloop.sdk.version import __version__

POSTHOG_API_KEY = "phc_JMTeAfG8OpaPsyHzSBtqquMvko1fmOHcW0gyqLCrF3t"
SENTRY_INGESTION_ENDPOINT = (
    "https://b4f74304f2541ee6781edd8c81b0773c@o4505278734663680.ingest.us.sentry.io/"
    + "4507109322260480"
)


class Telemetry:
    ANON_ID_PATH = str(Path.home() / ".cache" / "traceloop" / "telemetry_anon_id")
    UNKNOWN_ANON_ID = "UNKNOWN"

    _sentry: sentry_sdk.Client = None
    _posthog: Posthog = None

    def __new__(cls) -> "Telemetry":
        if not hasattr(cls, "instance"):
            obj = cls.instance = super(Telemetry, cls).__new__(cls)
            obj._telemetry_enabled = (
                os.getenv("TRACELOOP_TELEMETRY") or "true"
            ).lower() == "true" and "pytest" not in sys.modules

            if obj._telemetry_enabled:
                obj._posthog = Posthog(
                    project_api_key=POSTHOG_API_KEY,
                    host="https://app.posthog.com",
                )
                obj._sentry = sentry_sdk.Client(
                    dsn=SENTRY_INGESTION_ENDPOINT,
                    default_integrations=False,
                    release=__version__,
                )
                obj._curr_anon_id = None

                posthog_logger = logging.getLogger("posthog")
                posthog_logger.disabled = True

        return cls.instance

    def _anon_id(self) -> str:
        if self._curr_anon_id:
            return self._curr_anon_id

        try:
            if not os.path.exists(self.ANON_ID_PATH):
                os.makedirs(os.path.dirname(self.ANON_ID_PATH), exist_ok=True)
                with open(self.ANON_ID_PATH, "w") as f:
                    new_anon_id = str(uuid.uuid4())
                    f.write(new_anon_id)
                self._curr_anon_id = new_anon_id
            else:
                with open(self.ANON_ID_PATH, "r") as f:
                    self._curr_anon_id = f.read()
        except Exception:
            self._curr_anon_id = self.UNKNOWN_ANON_ID
        return self._curr_anon_id

    def _context(self) -> dict:
        return {
            "sdk": "python",
            "sdk_version": __version__,
        }

    def capture(self, event: str, event_properties: dict = {}) -> None:
        try:  # don't fail if telemetry fails
            if self._telemetry_enabled:
                self._posthog.capture(
                    self._anon_id(), event, {**self._context(), **event_properties}
                )
        except Exception:
            pass

    def log_exception(self, exception: Exception):
        try:  # don't fail if telemetry fails
            with sentry_sdk.Hub(self._sentry) as hub:
                hub.capture_exception(exception)
        except Exception:
            pass

    def feature_enabled(self, key: str):
        try:  # don't fail if telemetry fails
            if self._telemetry_enabled:
                return self._posthog.feature_enabled(key, self._anon_id())
        except Exception:
            pass
        return False
