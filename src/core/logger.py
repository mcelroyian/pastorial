import logging
import sys
from ..core import config

DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [%(agent_name)s|%(agent_id)s] - %(message)s"

# Custom Formatter to handle the agent_id
class AgentIdFormatter(logging.Formatter):
    """A custom log formatter that adds a default value for agent_id if it's missing."""
    def format(self, record):
        if not hasattr(record, 'agent_id'):
            record.agent_id = 'SYSTEM' # Default value for non-agent logs
        if not hasattr(record, 'agent_name'):
            record.agent_name = 'SYSTEM' # Default value for non-agent logs
        return super().format(record)

def setup_logging(default_level=DEFAULT_LOG_LEVEL, per_module_levels=None):
    """
    Configures logging for the application.

    Sets a default log level for the root logger and allows specifying
    different log levels for individual modules.

    Args:
        default_level: The default logging level for the root logger
                       (e.g., logging.INFO, logging.DEBUG).
        per_module_levels (dict, optional): A dictionary mapping logger names
                                           (e.g., 'src.agents.agent') to
                                           specific logging levels
                                           (e.g., logging.DEBUG).
                                           Defaults to None.
    """
    # Use the custom formatter
    formatter = AgentIdFormatter(LOG_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(default_level)

    # Add handlers to the root logger
    if not root_logger.hasHandlers(): # Avoid adding multiple handlers if called more than once
        root_logger.addHandler(console_handler)

        # File Handler (optional, based on config)
        if config.LOG_TO_FILE:
            file_handler = logging.FileHandler(config.LOG_FILE_PATH, mode=config.LOG_FILE_MODE)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    # Apply per-module log levels
    if per_module_levels:
        for logger_name, level in per_module_levels.items():
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(level)
            # Ensure handlers are propagated if not explicitly set for module loggers
            # and they don't have their own.
            # Typically, child loggers propagate to parent handlers by default.
            # If a module_logger doesn't have handlers and propagate is True (default),
            # its messages will be handled by the root_logger's handlers.
            # No explicit handler addition needed here unless specific per-module handlers are desired.

    # Example: How to get a logger in other modules
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("This is an info message from my_module.")
    #
    # To configure per-module levels:
    # custom_levels = {
    #     "src.agents.agent": logging.DEBUG,
    #     "src.tasks.task_manager": logging.WARNING,
    # }
    # setup_logging(default_level=logging.INFO, per_module_levels=custom_levels)

if __name__ == "__main__":
    # Example usage (for testing this module directly)
    setup_logging(logging.DEBUG)
    test_logger = logging.getLogger("my_test_app")
    test_logger.debug("This is a debug message.")
    test_logger.info("This is an info message.")
    test_logger.warning("This is a warning message.")
    test_logger.error("This is an error message.")
    test_logger.critical("This is a critical message.")