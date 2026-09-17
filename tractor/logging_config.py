import json
import logging

from tractor.credentials import Credentials, redact


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            redact(
                {
                    "level": record.levelname,
                    "event": record.getMessage(),
                    **{
                        key: getattr(record, key)
                        for key in (
                            "investigation_id",
                            "adapter",
                            "query_variant",
                            "duration_ms",
                            "result_count",
                            "error_category",
                            "status",
                        )
                        if hasattr(record, key)
                    },
                }
            )
        )


def configure_logging(debug: bool = False) -> None:
    Credentials()  # Register environment secrets before any application logging.
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("tractor")
    log.handlers = [handler]
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    log.propagate = False
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
