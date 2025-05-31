import logging
import sys

DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

def setup_logging(level=DEFAULT_LOG_LEVEL):
    """
    Configures the root logger for the application.
    """
    formatter = logging.Formatter(LOG_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add handlers to the root logger
    if not root_logger.hasHandlers(): # Avoid adding multiple handlers if called more than once
        root_logger.addHandler(console_handler)

    # Example: How to get a logger in other modules
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("This is an info message from my_module.")

if __name__ == "__main__":
    # Example usage (for testing this module directly)
    setup_logging(logging.DEBUG)
    test_logger = logging.getLogger("my_test_app")
    test_logger.debug("This is a debug message.")
    test_logger.info("This is an info message.")
    test_logger.warning("This is a warning message.")
    test_logger.error("This is an error message.")
    test_logger.critical("This is a critical message.")