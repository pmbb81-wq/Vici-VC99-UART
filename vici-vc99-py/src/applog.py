import os
import sys
import logging
import traceback
import datetime


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LOG_FILE = os.path.join(get_base_dir(), "vici_vc99_log.txt")


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    for h in list(logger.handlers):
        logger.removeHandler(h)

    fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.info("=" * 60)
    logger.info("VICI VC99 start")
    logger.info("Czas: %s", datetime.datetime.now().isoformat())
    logger.info("Python: %s", sys.version)
    logger.info("Plik wykonywalny: %s", sys.executable)
    logger.info("Frozen: %s", getattr(sys, "frozen", False))
    logger.info("Sys.path: %s", sys.path)
    logger.info("=" * 60)

    def excepthook(exc_type, exc_value, exc_tb):
        logger.error(
            "Nieobsluzony wyjatek:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook

    try:
        import faulthandler

        fh_fault = open(LOG_FILE, "a", encoding="utf-8")
        faulthandler.enable(file=fh_fault)
    except Exception:
        pass

    return logger


log = logging.getLogger()
