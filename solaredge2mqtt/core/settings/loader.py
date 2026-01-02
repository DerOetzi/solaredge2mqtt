import sys
from os import path
from typing import Any

import yaml

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.settings.migrator import ConfigurationMigrator
from solaredge2mqtt.core.settings.models import ServiceSettings

DOCKER_SECRETS_DIR = "/run/secrets"
CONFIG_DIR = "config"
CONFIG_FILE = "config/configuration.yml"
SECRETS_FILE = "config/secrets.yml"

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
            f"Secret '{secret_key}' not found in {SECRETS_FILE}. "
            f"Please ensure the secret is defined."
        )

# Register the !secret constructor
SecretLoader.add_constructor("!secret", secret_constructor)

class ConfigurationLoader:
    @staticmethod
    def load_configuration(override_data: dict[str, any] = None):
        config_exists = path.exists(CONFIG_FILE)
        
        if not config_exists:
            logger.info(
                f"{CONFIG_FILE} not found. "
                "Performing automatic migration from environment variables."
            )
            return ConfigurationLoader._migrate_from_environment()
        
        if ConfigurationLoader._is_file_empty(CONFIG_FILE):
            logger.info(
                f"{CONFIG_FILE} is empty. "
                "Performing automatic migration from environment variables."
            )
            return ConfigurationLoader._migrate_from_environment()

        if path.exists(SECRETS_FILE):
            SecretLoader.secrets = ConfigurationLoader._load_yaml_file(SECRETS_FILE)
            logger.info(f"Loaded secrets from {SECRETS_FILE}")

        config_data = ConfigurationLoader._load_yaml_file(
            CONFIG_FILE, use_secret_loader=True
        )
        logger.info(f"Loaded configuration from {CONFIG_FILE}")

        if override_data:
            config_data = ConfigurationLoader._deep_merge(config_data, override_data)

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
        filepath: str, use_secret_loader: bool = False
    ) -> dict[str, any]:
        
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
    def _migrate_from_environment():
        from solaredge2mqtt.core.settings.models import ServiceSettings
        
        migrator = ConfigurationMigrator(model_class=ServiceSettings)
        
        env_config_data, env_secrets_data = migrator.extract_from_environment()
        
        merged_env_data = ConfigurationLoader._deep_merge(
            env_config_data, env_secrets_data
        )
        
        try:
            validated_model = ServiceSettings(**merged_env_data)
            
            validated_data = validated_model.model_dump(exclude_none=True)
            
            config_data, secrets_data = migrator.extract_and_prepare_for_export(
                validated_data
            )
            
            migrator.write_yaml_files(
                config_data, secrets_data, CONFIG_FILE, SECRETS_FILE
            )
            
            logger.info(
                f"Migration complete. Created {CONFIG_FILE} and {SECRETS_FILE}. "
                f"Configuration validated through Pydantic model."
            )
            
            return validated_model
                
        except Exception as e:
            logger.warning(
                f"Pydantic validation failed during migration: {e}. "
                f"Falling back to basic migration."
            )
            
            migrator.write_yaml_files(
                env_config_data, env_secrets_data, CONFIG_FILE, SECRETS_FILE
            )
            
            logger.info(
                f"Migration complete. Created {CONFIG_FILE} and {SECRETS_FILE}. "
                f"Please review the files and restart the service."
            )
            
            sys.exit(0)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigurationLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
