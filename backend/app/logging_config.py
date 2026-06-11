import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

from app.config import BACKEND_DIR

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_DIR = BACKEND_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
FILE_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s:%(lineno)d: %(message)s"

_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    request_id_filter = RequestIdFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt="%H:%M:%S"))
    console_handler.addFilter(request_id_filter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    file_handler.addFilter(request_id_filter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # App code may log at DEBUG (goes to the file only); third-party stays at INFO.
    logging.getLogger("app").setLevel(logging.DEBUG)
