from os import chmod, environ, listdir, makedirs, path
from typing import Any, get_args, get_origin

import yaml
from pydantic import BaseModel, SecretStr, ValidationError

from solaredge2mqtt.core.logging import logger

DOCKER_SECRETS_DIR = "/run/secrets"


class EnvironmentReader:
    PREFIX = "se2mqtt_"

    @classmethod
    def read_all(cls) -> dict[str, str]:
        config = {}

        for key, value in cls._read_environment():
            config[key] = value

        for key, value in cls._read_dotenv():
            if key not in config:
                config[key] = value

        for key, value in cls._read_secrets():
            if key not in config:
                config[key] = value

        return config

    @classmethod
    def _read_environment(cls):
        for key, value in environ.items():
            if cls._has_prefix(key):
                yield key, value

    @classmethod
    def _read_secrets(cls):
        if path.exists(DOCKER_SECRETS_DIR) and path.isdir(DOCKER_SECRETS_DIR):
            for filename in listdir(DOCKER_SECRETS_DIR):
                if cls._has_prefix(filename):
                    with open(
                        path.join(DOCKER_SECRETS_DIR, filename),
                        "r",
                        encoding="utf-8",
                    ) as f:
                        yield filename, f.read().strip()

    @classmethod
    def _read_dotenv(cls):
        try:
            if path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        line = line.strip()
                        if cls._has_prefix(line) and "=" in line:
                            key, value = line.split("=", 1)
                            yield key, value.strip()
        except FileNotFoundError:
            logger.debug(
                "EnvironmentReader: '.env' file not found while attempting "
                "to read environment-style settings."
            )

    @staticmethod
    def _has_prefix(key: str) -> bool:
        return key.lower().startswith(EnvironmentReader.PREFIX)


class SecretReference:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def __repr__(self):
        return f"!secret {self.secret_key}"


def secret_representer(dumper, data):
    return yaml.ScalarNode(
        tag="!secret",
        value=data.secret_key,
        style="",
    )


class ConfigDumper(yaml.SafeDumper):
    pass


_original_choose_scalar_style = ConfigDumper.choose_scalar_style


def _custom_choose_scalar_style(self):
    if self.event.tag == "!secret":
        return ""
    return _original_choose_scalar_style(self)


ConfigDumper.choose_scalar_style = _custom_choose_scalar_style
ConfigDumper.add_representer(SecretReference, secret_representer)


class ConfigurationMigrator:
    def __init__(self, model_class: type[BaseModel]):
        self.model_class = model_class
        self.secret_fields = self._identify_secret_fields(model_class)

    def _identify_secret_fields(
        self, model: type[BaseModel], prefix: str = ""
    ) -> dict[str, list[str]]:
        secret_fields: dict[str, list[str]] = {}

        for field_name, field_info in model.model_fields.items():
            field_path = f"{prefix}.{field_name}" if prefix else field_name
            annotation = field_info.annotation

            self._process_field_annotation(
                annotation, field_name, field_path, prefix, secret_fields
            )

        return secret_fields

    def _process_field_annotation(
        self,
        annotation: Any,
        field_name: str,
        field_path: str,
        prefix: str,
        secret_fields: dict[str, list[str]],
    ) -> None:
        """Process a field annotation to identify secrets."""
        origin = get_origin(annotation)
        if origin is not None:
            self._process_generic_annotation(
                annotation, field_name, field_path, prefix, secret_fields
            )

        if self._is_secret_type(annotation):
            self._add_secret_field(field_name, prefix, secret_fields)
            return

        if self._is_base_model_type(annotation):
            self._merge_nested_secrets(annotation, field_path, secret_fields)

    def _process_generic_annotation(
        self,
        annotation: Any,
        field_name: str,
        field_path: str,
        prefix: str,
        secret_fields: dict[str, list[str]],
    ) -> None:
        """Process generic type annotations (e.g., Optional, Union)."""
        args = get_args(annotation)
        for arg in args:
            if self._is_secret_type(arg):
                self._add_secret_field(field_name, prefix, secret_fields)
                break

            if self._is_base_model_type(arg):
                self._merge_nested_secrets(arg, field_path, secret_fields)

    @staticmethod
    def _is_secret_type(annotation: Any) -> bool:
        """Check if annotation is SecretStr type."""
        if annotation is SecretStr:
            return True
        return isinstance(annotation, type) and issubclass(
            annotation, SecretStr
        )

    @staticmethod
    def _is_base_model_type(annotation: Any) -> bool:
        """Check if annotation is BaseModel type."""
        return isinstance(annotation, type) and issubclass(
            annotation, BaseModel
        )

    def _add_secret_field(
        self,
        field_name: str,
        prefix: str,
        secret_fields: dict[str, list[str]],
    ) -> None:
        """Add a secret field to the tracking dictionary."""
        parent_key = prefix or field_name.split(".")[0]
        if parent_key not in secret_fields:
            secret_fields[parent_key] = []
        secret_fields[parent_key].append(field_name)

    def _merge_nested_secrets(
        self,
        model: type[BaseModel],
        field_path: str,
        secret_fields: dict[str, list[str]],
    ) -> None:
        """Merge secrets from nested models."""
        nested_secrets = self._identify_secret_fields(model, field_path)
        for key, fields in nested_secrets.items():
            if key not in secret_fields:
                secret_fields[key] = []
            secret_fields[key].extend(fields)

    def migrate(self) -> BaseModel:
        env_data = EnvironmentReader.read_all()

        parsed_data = self._parse_environment_to_dict(env_data)

        try:
            validated_model = self.model_class(**parsed_data)
            logger.info(
                "Environment variables validated successfully with "
                "Pydantic model"
            )
            return validated_model
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise

    def _parse_environment_to_dict(
        self, env_data: dict[str, str]
    ) -> dict[str, Any]:
        config_data = {}

        for key, value in env_data.items():
            key = key.lower().strip()[8:]
            subkeys = key.split("__")

            typed_value = value.strip()
            self._insert_nested_key(config_data, subkeys, typed_value)

        return config_data

    def _insert_nested_key(
        self, container: dict, keys: list[str], value: Any
    ) -> None:
        key, i = self._identify_key_and_position(keys)
        key, idx, next_container = self._get_or_initialize_nested_container(
            container, key, i
        )
        
        # Insert value or recurse deeper
        if len(keys) == 1:
            self._set_final_value(container, key, idx, value)
        else:
            self._insert_nested_key(next_container, keys[1:], value)

    @staticmethod
    def _identify_key_and_position(keys: list[str]) -> tuple[str, int]:
        key = keys[0]
        for i in range(len(key) - 1, -1, -1):
            if not key[i].isdigit():
                break
        return key, i

    @staticmethod
    def _get_or_initialize_nested_container(
        container: dict, key: str, i: int
    ) -> tuple[str, int | str, dict | list]:
        prefix, idx = key[: i + 1], key[i + 1 :]
        if idx.isdigit():
            return ConfigurationMigrator._init_list_container(
                container, prefix, int(idx)
            )
        return ConfigurationMigrator._init_dict_container(container, key)

    @staticmethod
    def _init_list_container(
        container: dict, key: str, idx: int
    ) -> tuple[str, int, dict]:
        """Initialize or get a list-based nested container."""
        if key not in container or not isinstance(container[key], list):
            container[key] = []
        while len(container[key]) <= idx:
            container[key].append({})
        return key, idx, container[key][idx]

    @staticmethod
    def _init_dict_container(
        container: dict, key: str
    ) -> tuple[str, str, dict]:
        """Initialize or get a dict-based nested container."""
        if key not in container or not isinstance(container[key], dict):
            container[key] = {}
        return key, key, container[key]

    @staticmethod
    def _set_final_value(
        container: dict[str, Any], key: str, idx: int | str, value: Any
    ) -> None:
        """Set the final value in the container."""
        if isinstance(container[key], list):
            container[key][idx] = value
        else:
            container[key] = value

    def export_to_yaml(
        self, model: BaseModel, config_file: str, secrets_file: str
    ) -> None:
        validated_data = model.model_dump(exclude_none=True)

        config_data, secrets_data = self._extract_secrets(validated_data)

        config_data = self._ensure_proper_types(config_data, model)

        # Remove any remaining None values from nested structures
        config_data = self._remove_null_values(config_data)

        self._write_yaml_files(
            config_data, secrets_data, config_file, secrets_file
        )

    def _ensure_proper_types(self, data: dict, model: BaseModel) -> dict:
        result = {}
        for key, value in data.items():
            result[key] = self._process_field_value(key, value, model)
        return result

    def _process_field_value(
        self, key: str, value: Any, model: BaseModel
    ) -> Any:
        """Process a single field value to ensure proper type."""
        if key not in model.model_fields:
            return value

        field_info = model.model_fields[key]
        annotation = field_info.annotation

        if isinstance(value, dict) and hasattr(annotation, "model_fields"):
            return self._ensure_proper_types(value, annotation)

        if self._is_simple_type(value):
            return value

        if hasattr(value, "value"):
            return value.value

        return value

    @staticmethod
    def _is_simple_type(value: Any) -> bool:
        """Check if value is a simple type that needs no conversion."""
        return isinstance(value, (list, bool, int, float, SecretReference))

    @staticmethod
    def _remove_null_values(obj: Any) -> Any:
        """
        Recursively remove None values from nested dictionaries and lists.

        Args:
            obj: The object to clean (dict, list, or other)

        Returns:
            Cleaned object without None values
        """
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if v is None:
                    continue
                cleaned_value = ConfigurationMigrator._remove_null_values(v)
                # Skip empty dicts that result from removing all None values
                if isinstance(cleaned_value, dict) and not cleaned_value:
                    continue
                result[k] = cleaned_value
            return result
        elif isinstance(obj, list):
            return [
                ConfigurationMigrator._remove_null_values(item)
                for item in obj
                if item is not None
            ]
        return obj

    def _extract_secrets(self, validated_data: dict) -> tuple[dict, dict]:
        import copy

        config_data = copy.deepcopy(validated_data)
        secrets_data = {}

        for section, fields in self.secret_fields.items():
            if section in config_data:
                self._process_section_secrets(
                    config_data, secrets_data, section, fields
                )

        return config_data, secrets_data

    def _process_section_secrets(
        self,
        config_data: dict,
        secrets_data: dict,
        section: str,
        fields: list[str],
    ) -> None:
        """Process secrets for a specific section."""
        section_data = config_data[section]
        if not isinstance(section_data, dict):
            return

        for field in fields:
            if field in section_data:
                self._extract_single_secret(
                    section_data, secrets_data, section, field
                )

    @staticmethod
    def _extract_single_secret(
        section_data: dict,
        secrets_data: dict,
        section: str,
        field: str,
    ) -> None:
        """Extract a single secret field."""
        secret_key = f"{section}_{field}"
        secret_value = section_data.pop(field)

        if isinstance(secret_value, SecretStr):
            secrets_data[secret_key] = secret_value.get_secret_value()
        else:
            secrets_data[secret_key] = secret_value

        section_data[field] = SecretReference(secret_key)

    def extract_from_environment(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        env_data = EnvironmentReader.read_all()
        parsed_data = self._parse_environment_to_dict(env_data)

        try:
            validated_model = self.model_class(**parsed_data)
            validated_data = validated_model.model_dump(exclude_none=True)
            config_data, secrets_data = self._extract_secrets(validated_data)
            config_data = self._ensure_proper_types(
                config_data, validated_model
            )
            # Remove any remaining None values from nested structures
            config_data = self._remove_null_values(config_data)
            return config_data, secrets_data
        except ValidationError as e:
            logger.error(
                f"Validation failed during extract_from_environment: {e}"
            )
            raise

    def write_yaml_files(
        self,
        config_data: dict,
        secrets_data: dict,
        config_file: str,
        secrets_file: str,
    ) -> None:
        self._write_yaml_files(
            config_data, secrets_data, config_file, secrets_file
        )

    def _write_yaml_files(
        self,
        config_data: dict,
        secrets_data: dict,
        config_file: str,
        secrets_file: str,
    ) -> None:
        config_dir = path.dirname(config_file)
        if config_dir and not path.exists(config_dir):
            try:
                makedirs(config_dir, exist_ok=True)
                logger.info(f"Created config directory: {config_dir}")
            except PermissionError as e:
                logger.error(
                    f"Permission denied creating directory {config_dir}: {e}"
                )
                raise

        try:
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    Dumper=ConfigDumper,
                )
            logger.info(f"Configuration written to {config_file}")
        except PermissionError as e:
            logger.error(
                f"Permission denied writing configuration file "
                f"{config_file}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Error writing configuration file {config_file}: {e}"
            )
            raise

        if secrets_data:
            try:
                with open(secrets_file, "w", encoding="utf-8") as f:
                    yaml.safe_dump(
                        secrets_data,
                        f,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                    )
                chmod(secrets_file, 0o600)
                logger.info(f"Secrets written to {secrets_file}")
                logger.warning(
                    f"IMPORTANT: {secrets_file} contains sensitive data. "
                    f"Keep it secure and do not commit it to version "
                    f"control!"
                )
            except PermissionError as e:
                logger.error(
                    f"Permission denied writing secrets file "
                    f"{secrets_file}: {e}"
                )
                raise
            except Exception as e:
                logger.error(f"Error writing secrets file {secrets_file}: {e}")
                raise
