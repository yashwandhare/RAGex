"""
Structured Logging Configuration
=================================
Production-ready logging with colored console output for development.
Provides clear, scannable logs for debugging and monitoring.
"""
import logging
import sys
from typing import Optional
from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """
    Custom log formatter with ANSI color codes.
    
    Makes logs easier to scan during development:
    - Errors are red (immediate attention)
    - Warnings are yellow (caution)
    - Info is green (success/progress)
    - Debug is cyan (detailed info)
    
    Colors only work in terminals that support ANSI codes.
    Most modern terminals (Linux, macOS, Windows 10+) support this.
    """
    
    # ANSI color codes for terminal output
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan - detailed information
        'INFO': '\033[32m',       # Green - success/progress
        'WARNING': '\033[33m',    # Yellow - caution
        'ERROR': '\033[31m',      # Red - errors
        'CRITICAL': '\033[35m',   # Magenta - critical failures
    }
    RESET = '\033[0m'  # Reset to default color
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.
        
        Wraps the level name (INFO, ERROR, etc.) with color codes.
        The rest of the message remains uncolored for readability.
        
        Args:
            record: Log record to format
        
        Returns:
            str: Formatted log message with ANSI colors
        """
        # Get color for this log level
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Add color codes around level name
        # Example: INFO becomes \033[32mINFO\033[0m
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # Let parent formatter handle the rest (timestamp, message, etc.)
        return super().format(record)


def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger instance.
    
    Creates a logger with:
    - Colored console output for development
    - Configurable log level from settings
    - Prevents duplicate handlers if called multiple times
    - Standardized format: timestamp | level | module | message
    
    Usage:
        from app.core.logger import setup_logger
        logger = setup_logger(__name__)
        logger.info("Application started")
        logger.error("Something went wrong")
    
    Args:
        name: Logger name (typically __name__ from calling module)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # ==================== CREATE LOGGER ====================
    # Get or create logger for this module
    logger = logging.getLogger(name)
    
    # Set level from configuration
    # Converts string like "INFO" to logging.INFO constant
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # ==================== PREVENT DUPLICATE HANDLERS ====================
    # If logger already has handlers, it's been initialized before
    # Return existing logger to avoid duplicate log messages
    if logger.handlers:
        return logger
    
    # ==================== CONSOLE HANDLER ====================
    # Logs to stdout (visible in terminal/console)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Handler shows all levels
    
    # ==================== FORMATTER ====================
    # Create colored formatter with timestamp and module info
    # Format: HH:MM:SS | LEVEL | module.name | message
    formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'  # Short time format (hour:minute:second)
    )
    
    console_handler.setFormatter(formatter)
    
    # ==================== ATTACH HANDLER ====================
    logger.addHandler(console_handler)
    
    # ==================== PREVENT PROPAGATION ====================
    # Don't pass logs to parent loggers (prevents duplicates)
    logger.propagate = False
    
    return logger


# ==================== PRODUCTION ENHANCEMENTS ====================
# For production deployment, consider adding:
#
# 1. File Logging:
#    - Rotate logs daily/weekly to prevent disk fill
#    - Store in persistent volume
#    - Example: RotatingFileHandler or TimedRotatingFileHandler
#
# 2. Structured Logging:
#    - JSON format for log aggregation tools
#    - Include request IDs, user IDs, etc.
#    - Example: python-json-logger
#
# 3. Remote Logging:
#    - Send to centralized logging service
#    - Examples: CloudWatch, Datadog, Elasticsearch
#
# 4. Performance Metrics:
#    - Log response times
#    - Track error rates
#    - Monitor resource usage
#
# Example file logging setup (add to setup_logger if needed):
#
# if settings.ENVIRONMENT == "production":
#     file_handler = RotatingFileHandler(
#         "logs/app.log",
#         maxBytes=10_000_000,  # 10MB
#         backupCount=5
#     )
#     file_handler.setFormatter(logging.Formatter(
#         '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
#     ))
#     logger.addHandler(file_handler)