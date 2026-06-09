from pathlib import Path

from config.settings import get_config


def get_required_dir(env_name: str) -> Path:
    """Get and validate a required directory from config.
    
    Args:
        env_name: Name of environment variable to read.
        
    Returns:
        Path object pointing to the directory.
        
    Raises:
        OSError: If environment variable is not set or path doesn't exist.
        NotADirectoryError: If path exists but is not a directory.
    """
    # Try to get from config first, then fall back to environment
    cfg = get_config()
    value = None
    
    # Map common env names to config paths
    config_mapping = {
        "CHURN_MODEL_DIR": "model.model_dir",
        "LOGS_DIR": "logging.logs_dir",
    }
    
    if env_name in config_mapping:
        try:
            value = cfg.get(config_mapping[env_name])
        except Exception:
            pass
    
    if not value:
        import os
        value = os.getenv(env_name)
    
    if not value:
        raise OSError(f"Missing required environment variable: {env_name}")

    path = Path(value)

    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    return path


CHURN_MODEL_DIR = get_required_dir("CHURN_MODEL_DIR")
