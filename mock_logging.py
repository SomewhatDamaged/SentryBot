import sys
import traceback as tb

class MockLogger:
    def __init__(self):
        pass

    def info(self, msg, *args):
        print("INFO: " + msg % args if args else msg)

    def error(self, msg, *args):
        print("ERROR: " + msg % args if args else msg)

    def debug(self, msg, *args):
        print("DEBUG: " + msg % args if args else msg)

    def warning(self, msg, *args):
        print("WARNING: " + msg % args if args else msg)

    def exception(self, msg: str = "", *args):
        _, ex, _ = sys.exc_info()
        print("TRACEBACK: " + ''.join(tb.format_exception(None, ex, ex.__traceback__)).strip())