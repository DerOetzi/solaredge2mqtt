import argparse

from solaredge2mqtt.service import run


def main():
    parser = argparse.ArgumentParser(
        description="SolarEdge2MQTT - Bridge SolarEdge data to MQTT"
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="config",
        help="Path to configuration directory (default: config)",
    )
    args = parser.parse_args()
    
    run(config_dir=args.config_dir)


if __name__ == "__main__":
    main()
