import os
import sys
import faulthandler
import traceback
import threading

# Set environment variables before importing GUI/native libraries.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Keep the file open for the entire process lifetime.
fault_log = open(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "crash.log"),
    "a",
    buffering=1,
    encoding="utf-8",
)

faulthandler.enable(file=fault_log, all_threads=True)


def exception_hook(exc_type, exc_value, exc_traceback):
    print("\nUnhandled exception:", file=fault_log)
    traceback.print_exception(
        exc_type,
        exc_value,
        exc_traceback,
        file=fault_log,
    )
    fault_log.flush()

    traceback.print_exception(
        exc_type,
        exc_value,
        exc_traceback,
    )


def thread_exception_hook(args):
    print(
        f"\nUnhandled thread exception in {args.thread.name}:",
        file=fault_log,
    )
    traceback.print_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        file=fault_log,
    )
    fault_log.flush()


sys.excepthook = exception_hook
threading.excepthook = thread_exception_hook

from src.gui.gui import Application


def main():
    local_path = os.path.dirname(os.path.realpath(__file__))

    print("Starting PIAHNO", file=fault_log)
    fault_log.flush()

    app = Application(local_path)

    print("Application returned normally", file=fault_log)
    fault_log.flush()

    return app


if __name__ == "__main__":
    try:
        application = main()
    except BaseException:
        traceback.print_exc(file=fault_log)
        fault_log.flush()
        raise
    finally:
        fault_log.flush()