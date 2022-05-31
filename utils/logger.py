import logging

FORMAT = "%(asctime)s %(levelname)s:: %(message)-50s"
LEVEL = logging.DEBUG

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LEVEL)

file_logger_handler = logging.FileHandler("log.log")
file_logger_handler.setLevel(LEVEL)
file_logger_handler.setFormatter(logging.Formatter(FORMAT))

stdout_logger_handler = logging.StreamHandler()
stdout_logger_handler.setLevel(LEVEL)
stdout_logger_handler.setFormatter(logging.Formatter(FORMAT))

LOGGER.addHandler(file_logger_handler)
# LOGGER.addHandler(stdout_logger_handler)
