import logging

def setup_logging(level: int = logging.INFO):
    """
    Set logging level
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )