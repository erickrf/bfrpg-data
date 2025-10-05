import logging
import uuid


def setup_logging(level: int = logging.INFO):
    """
    Set logging level
    """
    logging.basicConfig(level=level, format="%(message)s")


def generate_foundry_id() -> str:
    """
    Generate a 16 char id used in foundry.
    """
    return uuid.uuid4().hex[:16]
