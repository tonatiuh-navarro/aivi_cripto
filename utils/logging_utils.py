import logging


_LOGGING_LEVELS = {
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR
}
_MODE_MAPPING = {
    'overwrite': 'w',
    'append': 'a'
}
_MUTED_LOGGERS = [
    'parso.python.diff',
    'parso.cache.pickle',
    'parso',
    'parso.cache',
    'matplotlib.font_manager',
    'matplotlib.backends.backend_pdf'
]

def _setup_muted_loggers():
    """One-time setup of muted loggers"""
    for logger_name in _MUTED_LOGGERS:
        logging.getLogger(logger_name).disabled = True

# Call once at module level
_setup_muted_loggers()

def setup_logger(
    name: str,
    log_file: str = None,
    log_level: str = 'INFO',
    mode: str = 'append',
    console: bool = True,
    propagate: bool = False
) -> logging.Logger:
    if log_level not in _LOGGING_LEVELS:
        raise ValueError(f"log_level must be one of {list(_LOGGING_LEVELS.keys())}")
    
    if mode not in _MODE_MAPPING:
        raise ValueError(f"mode must be one of {list(_MODE_MAPPING.keys())}")

    logger = logging.getLogger(name)
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Set the logging level
    logger.setLevel(_LOGGING_LEVELS[log_level])

    # Configure the log format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(
            log_file,
            mode=_MODE_MAPPING[mode]
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    elif console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Set the propagation flag
    logger.propagate = propagate

    return logger


def setup_logger_for_child(
    parent_name: str,
    child_name: str,
    log_file: str = None,
    log_level: str = 'DEBUG',
    mode: str = 'append',
    console: bool = True,
    propagate: bool = False
) -> logging.Logger:
    logger_name = f'{parent_name}.{child_name}'
    return setup_logger(
        name=logger_name,
        log_level=log_level,
        log_file=log_file,
        mode=mode,
        console=console,
        propagate=propagate
    )
