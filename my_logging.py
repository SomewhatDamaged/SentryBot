import sys
import os
import traceback as tb
import logging
from logging import handlers

MAX_FILES = 10 # Number of log files to store


LOG = None

def make_logger() -> logging.Logger:
    global LOG
    LOG = logging.getLogger("sentrybot")

    fhandler: handlers.RotatingFileHandler | None = None
    if len(LOG.handlers) == 0:
        folder = "./.log/"
        new_folder = False
        if not os.path.exists(folder):
            os.makedirs(folder)
            new_folder = True
        if os.path.exists("./.debug"):
            LOG.level = logging.DEBUG
        else:
            LOG.level = logging.INFO
        file = "sentrybot.log"
        fhandler = handlers.RotatingFileHandler(
            filename=folder + file,
            encoding="utf-8",
            mode="a",
            maxBytes=10**7,
            backupCount=MAX_FILES,
        )
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
            datefmt="[%d/%m/%Y %H:%M]",
        )
        fhandler.setFormatter(fmt)
        if not new_folder:
            fhandler.doRollover()
        LOG.addHandler(fhandler)

        err_handler = logging.StreamHandler(stream=sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
            datefmt="[%d/%m/%Y %H:%M]",
        )
        err_handler.setFormatter(fmt)
        LOG.addHandler(err_handler)
    return LOG


def process_exception(msg: str = "", *args):
    _, ex, _ = sys.exc_info()
    if isinstance(LOG, logging.Logger):
        LOG.error("EXCEPTION: " + msg, *args)
        LOG.error("TRACEBACK: " + ''.join(tb.format_exception(None, ex, ex.__traceback__)).strip())



