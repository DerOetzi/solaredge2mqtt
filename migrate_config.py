#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from solaredge2mqtt.core.settings.migrator import ConfigDumper, ConfigurationMigrator


def _dump(data: dict) -> str:
    """Render a preview the same way the migration writes the file.

    `yaml.safe_dump` cannot represent a `SecretReference`, and every migrated
    configuration that has a password carries one, so the dry run has to use
    the dumper that knows the `!secret` tag.
    """
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        Dumper=ConfigDumper,
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Migrate SolarEdge2MQTT configuration from "
            "environment variables to YAML files."
        )
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=".env",
        help="Path to the .env file to read (default: .env)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=".",
        help="Output directory for YAML files (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Preview the migration without writing files",
    )
    parser.add_argument(
        "--backup",
        "-b",
        action="store_true",
        help="Create backup of existing configuration files",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    config_file = output_dir / "configuration.yml"
    secrets_file = output_dir / "secrets.yml"

    if args.backup:
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if config_file.exists():
            backup_path = config_file.with_suffix(f".yml.backup.{timestamp}")
            config_file.rename(backup_path)
            print(f"Created backup: {backup_path}")
        if secrets_file.exists():
            backup_path = secrets_file.with_suffix(f".yml.backup.{timestamp}")
            secrets_file.rename(backup_path)
            print(f"Created backup: {backup_path}")

    print("Starting migration...")
    print(f"Reading configuration from environment variables and {args.input}")

    if not Path(args.input).exists():
        print(
            f"NOTE: {args.input} does not exist, "
            "reading environment variables and Docker secrets only."
        )

    migrator = ConfigurationMigrator(dotenv_path=args.input)
    config_data, secrets_data = migrator.extract_from_environment()

    if args.dry_run:
        print("\n=== DRY RUN MODE - No files will be written ===\n")
        print(f"\n--- Configuration ({config_file}) ---")
        print(_dump(config_data))
        print(f"\n--- Secrets ({secrets_file}) ---")
        print(_dump(secrets_data))
        print("\n=== END DRY RUN ===")
    else:
        migrator.write_yaml_files(
            config_data, secrets_data, str(config_file), str(secrets_file)
        )
        print("\nMigration complete!")
        print(f"  - Configuration written to: {config_file}")
        print(f"  - Secrets written to: {secrets_file}")
        print(
            "\nIMPORTANT: Please review the files and ensure all settings are correct."
        )
        print(f"WARNING: {secrets_file} contains sensitive data. Keep it secure!")


if __name__ == "__main__":
    main()
