from os import path
from pathlib import Path
from shutil import copy2
from sys import exit as sys_exit
from typing import Any

import yaml
from pydantic import ValidationError

from solaredge2mqtt.config import get_example_files
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.settings.migrator import (
    ConfigurationMigrator,
    EnvironmentReader,
)
from solaredge2mqtt.core.settings.models import ServiceSettings


class SecretLoader(yaml.SafeLoader):
    secrets: dict[str, Any] = {}


def secret_constructor(loader: SecretLoader, node: yaml.ScalarNode) -> Any:
    secret_key = loader.construct_scalar(node)
    keys = secret_key.split(".")

    value = SecretLoader.secrets
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        raise ValueError(
            f"Secret '{secret_key}' not found in secrets file. "
            f"Please ensure the secret is defined."
        )


# Register the !secret constructor
SecretLoader.add_constructor("!secret", secret_constructor)


class ConfigurationLoader:
    @staticmethod
    def load_configuration(
        config_dir: str = "config", override_data: dict[str, any] = None
    ):
        config_file = path.join(config_dir, "configuration.yml")
        secrets_file = path.join(config_dir, "secrets.yml")
        
        config_exists = path.exists(config_file)

        if not config_exists:
            logger.info(
                f"{config_file} not found. "
                "Performing automatic migration from environment variables."
            )
            return ConfigurationLoader._migrate_from_environment(
                config_file, secrets_file
            )

        if ConfigurationLoader._is_file_empty(config_file):
            logger.info(
                f"{config_file} is empty. "
                "Performing automatic migration from environment variables."
            )
            return ConfigurationLoader._migrate_from_environment(
                config_file, secrets_file
            )

        if path.exists(secrets_file):
            SecretLoader.secrets = ConfigurationLoader._load_yaml_file(
                secrets_file
            )
            logger.info(f"Loaded secrets from {secrets_file}")

        config_data = ConfigurationLoader._load_yaml_file(
            config_file, use_secret_loader=True
        )
        logger.info(f"Loaded configuration from {config_file}")

        if override_data:
            config_data = ConfigurationLoader._deep_merge(
                config_data, override_data
            )

        return ServiceSettings(**config_data)

    @staticmethod
    def _is_file_empty(filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return len(content) == 0
        except (FileNotFoundError, PermissionError):
            return False

    @staticmethod
    def _load_yaml_file(
        filepath: str,
        use_secret_loader: bool = False,
    ) -> dict[str, Any]:

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                if use_secret_loader:
                    data = yaml.load(f, Loader=SecretLoader)
                else:
                    data = yaml.safe_load(f)
                return data if data is not None else {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {filepath}: {e}")
            raise
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading file {filepath}: {e}")
            raise

    @staticmethod
    def _migrate_from_environment(config_file: str, secrets_file: str):
        # First check if there are any environment variables to migrate
        env_config = EnvironmentReader.read_all()
        
        if not env_config:
            # No environment variables found - new installation scenario
            logger.info(
                "No environment variables or .env file found. "
                "This appears to be a new installation."
            )
            ConfigurationLoader._copy_example_files(
                config_file, secrets_file
            )
            logger.info(
                f"\nConfiguration files created from examples:\n"
                f"  - {config_file}\n"
                f"  - {secrets_file}\n\n"
                f"Please edit these files with your settings and restart."
            )
            sys_exit(0)
        
        # Environment variables found, proceed with migration
        migrator = ConfigurationMigrator(model_class=ServiceSettings)

        try:
            validated_model = migrator.migrate()

            migrator.export_to_yaml(validated_model, config_file, secrets_file)

            logger.info(
                f"Migration complete. Created {config_file} and "
                f"{secrets_file}. Configuration validated through "
                f"Pydantic model."
            )

            return validated_model

        except (ValidationError, OSError, yaml.YAMLError) as e:
            logger.error(
                f"Migration failed: {e}. "
                f"Please check your environment variables and try again."
            )
            raise
    
    @staticmethod
    def _copy_example_files(config_file: str, secrets_file: str):
        """Copy example configuration files to target locations."""
        # Get the config directory from the target file path
        config_dir = path.dirname(config_file)
        
        # Ensure the config directory exists
        Path(config_dir).mkdir(parents=True, exist_ok=True)
        
        # Get example file paths from the package
        config_example, secrets_example = get_example_files()
        
        try:
            if path.exists(config_example):
                copy2(config_example, config_file)
                logger.info(f"Copied example to {config_file}")
            else:
                logger.warning(
                    f"Example file not found: {config_example}. "
                    f"Creating empty {config_file}"
                )
                Path(config_file).touch()
            
            if path.exists(secrets_example):
                copy2(secrets_example, secrets_file)
                # Set restrictive permissions on secrets file
                Path(secrets_file).chmod(0o600)
                logger.info(f"Copied example to {secrets_file}")
            else:
                logger.warning(
                    f"Example file not found: {secrets_example}. "
                    f"Creating empty {secrets_file}"
                )
                Path(secrets_file).touch()
                Path(secrets_file).chmod(0o600)
                
        except (OSError, IOError) as e:
            logger.error(f"Error copying example files: {e}")
            raise

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:

        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigurationLoader._deep_merge(
                    result[key], value
                )
            else:
                result[key] = value
        return result
