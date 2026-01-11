"""Configuration example files for SolarEdge2MQTT."""
from os import path


def get_example_files() -> tuple[str, str]:
    """
    Get paths to example configuration files from the package.
    
    Returns:
        tuple[str, str]: Paths to configuration.yml.example and
        secrets.yml.example files
    """
    # Use __file__ to get the directory of this module
    config_dir = path.dirname(__file__)
    config_example = path.join(config_dir, "configuration.yml.example")
    secrets_example = path.join(config_dir, "secrets.yml.example")
    return config_example, secrets_example
