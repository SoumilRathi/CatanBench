"""
Logging utilities for CatanBench.

This module provides logging configuration and utilities for
tournament management and game analysis.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_tournament_logging(
    log_file: Optional[str] = None,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for tournament management.
    
    Args:
        log_file: Path to log file (optional)
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("catanbench")
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Set level
    logger.setLevel(getattr(logging, level.upper()))
    
    # Create formatter
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(format_string)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_game_logger(game_id: str) -> logging.Logger:
    """
    Get a logger for a specific game.
    
    Args:
        game_id: Unique game identifier
        
    Returns:
        Logger instance for the game
    """
    logger_name = f"catanbench.game.{game_id}"
    return logging.getLogger(logger_name)