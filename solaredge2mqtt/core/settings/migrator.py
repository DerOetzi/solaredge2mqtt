

from os import environ, listdir, makedirs, path
from typing import Any, Generator, get_args, get_origin

import yaml
from pydantic import BaseModel
from pydantic.fields import FieldInfo

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
    def _read_environment(cls) -> Generator[tuple[str, str], any, any]:
        for key, value in environ.items():
            if cls._has_prefix(key):
                yield key, value

    @classmethod
    def _read_secrets(cls) -> Generator[tuple[str, str], any, any]:
        if path.exists(DOCKER_SECRETS_DIR) and path.isdir(DOCKER_SECRETS_DIR):
            for filename in listdir(DOCKER_SECRETS_DIR):
                if cls._has_prefix(filename):
                    with open(
                        path.join(DOCKER_SECRETS_DIR, filename), "r", encoding="utf-8"
                    ) as f:
                        yield filename, f.read()

    @classmethod
    def _read_dotenv(cls) -> Generator[tuple[str, str], any, any]:
        try:
            if path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        line = line.strip()
                        if cls._has_prefix(line) and "=" in line:
                            key, value = line.split("=", 1)
                            yield key, value
        except FileNotFoundError:
            pass

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
    SENSITIVE_FIELDS = {
        "mqtt": ["password"],
        "monitoring": ["password", "site_id"],
        "wallbox": ["password", "serial"],
        "influxdb": ["token"],
        "weather": ["api_key"],
    }

    def __init__(self, model_class: type[BaseModel] | None = None):
        self.model_class = model_class
        self._field_types_cache: dict[str, type] = {}
        if model_class:
            self._build_field_types_map(model_class)

    def _build_field_types_map(
        self, model: type[BaseModel], prefix: str = ""
    ) -> None:
        for field_name, field_info in model.model_fields.items():
            field_path = f"{prefix}.{field_name}" if prefix else field_name
            field_type = field_info.annotation
            
            origin = get_origin(field_type)
            
            if origin is list:
                args = get_args(field_type)
                if args:
                    list_item_type = args[0]
                    self._field_types_cache[field_path] = list_item_type
                else:
                    self._field_types_cache[field_path] = str
            elif origin is type(None) or origin is Any:
                args = get_args(field_type)
                if args:
                    actual_type = args[0] if args[0] is not type(None) else (args[1] if len(args) > 1 else str)
                    self._field_types_cache[field_path] = actual_type
                    
                    if isinstance(actual_type, type) and issubclass(actual_type, BaseModel):
                        self._build_field_types_map(actual_type, field_path)
            else:
                self._field_types_cache[field_path] = field_type
                
                if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    self._build_field_types_map(field_type, field_path)

    def extract_from_environment(self) -> tuple[dict[str, Any], dict[str, Any]]:
        env_data = EnvironmentReader.read_all()
        config_data = {}

        for key, value in env_data.items():
            key = key.lower().strip()[8:]
            subkeys = key.split("__")
            
            field_path = ".".join(subkeys)
            field_type = self._get_field_type(field_path)
            
            typed_value = self._convert_to_type(value.strip(), field_type)
            self._insert_nested_key(config_data, subkeys, typed_value)

        secrets_data = self._extract_secrets(config_data)

        return config_data, secrets_data

    def _get_field_type(self, field_path: str) -> type:
        parts = field_path.split(".")
        
        for i in range(len(parts), 0, -1):
            path_to_check = ".".join(parts[:i])
            
            if path_to_check.endswith(tuple(str(d) for d in range(10))):
                base_path = path_to_check.rstrip("0123456789")
                if base_path in self._field_types_cache:
                    return self._field_types_cache[base_path]
            
            if path_to_check in self._field_types_cache:
                return self._field_types_cache[path_to_check]
        
        return str

    def _convert_to_type(self, value: str, target_type: type) -> Any:
        if not value:
            return value
        
        if target_type == bool or target_type is bool:
            value_lower = value.lower()
            if value_lower in ("true", "yes", "on"):
                return True
            if value_lower in ("false", "no", "off"):
                return False
            return bool(value)
        
        if target_type == int or target_type is int:
            try:
                return int(value)
            except ValueError:
                return value
        
        if target_type == float or target_type is float:
            try:
                return float(value)
            except ValueError:
                return value
        
        return value

    def _insert_nested_key(
        self, container: dict, keys: list[str], value: Any
    ) -> None:
        key, i = self._identify_key_and_position(keys)
        key, idx, next_container = self._get_or_initialize_nested_container(
            container, key, i
        )
        self._insert_value_in_container(
            container, keys, value, key, idx, next_container
        )

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
            key, idx = prefix, int(idx)
            if key not in container or not isinstance(container[key], list):
                container[key] = []
            while len(container[key]) <= idx:
                container[key].append({})
            next_container = container[key][idx]
        else:
            if key not in container or not isinstance(container[key], dict):
                container[key] = {}
            next_container = container[key]
        return key, idx, next_container

    def _insert_value_in_container(
        self,
        container: dict[str, Any],
        keys: list[str],
        value: Any,
        key: str,
        idx: int | str,
        next_container: dict | list,
    ) -> None:
        if len(keys) == 1:
            if isinstance(next_container, dict):
                if isinstance(container[key], list):
                    container[key][idx] = value
                else:
                    container[key] = value
            else:
                container[key] = value
        else:
            self._insert_nested_key(next_container, keys[1:], value)

    def _extract_secrets(self, config_data: dict) -> dict[str, Any]:
        secrets_data = {}

        for section, fields in self.SENSITIVE_FIELDS.items():
            if section in config_data:
                for field in fields:
                    if field in config_data[section]:
                        secret_key = f"{section}_{field}"
                        secrets_data[secret_key] = config_data[section].pop(field)
                        config_data[section][field] = SecretReference(secret_key)

        return secrets_data

    def extract_and_prepare_for_export(
        self, validated_data: dict
    ) -> tuple[dict, dict]:
        import copy

        config_data = copy.deepcopy(validated_data)
        secrets_data = {}

        for section, fields in self.SENSITIVE_FIELDS.items():
            if section in config_data:
                for field in fields:
                    if field in config_data[section]:
                        secret_key = f"{section}_{field}"
                        secrets_data[secret_key] = config_data[section].pop(field)
                        config_data[section][field] = SecretReference(secret_key)

        return config_data, secrets_data

    def write_yaml_files(
        self,
        config_data: dict,
        secrets_data: dict,
        config_file: str,
        secrets_file: str,
    ) -> None:
        
        config_dir = path.dirname(config_file)
        if config_dir and not path.exists(config_dir):
            makedirs(config_dir, exist_ok=True)
            logger.info(f"Created config directory: {config_dir}")

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
        except Exception as e:
            logger.error(f"Error writing configuration file {config_file}: {e}")
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
                logger.info(f"Secrets written to {secrets_file}")
                logger.warning(
                    f"IMPORTANT: {secrets_file} contains sensitive data. "
                    f"Keep it secure and do not commit it to version control!"
                )
            except Exception as e:
                logger.error(f"Error writing secrets file {secrets_file}: {e}")
                raise
