import json

import versioneer


def generate_static_version_file():
    versions = versioneer.get_versions()
    version_string = f"""# This file was generated automatically
import json
    
versions_json = '''{json.dumps(versions, indent=4)}'''

def get_versions() -> dict[str | bool | None]:
    return json.loads(versions_json)    

"""
    with open("solaredge2mqtt/_version.py", "w", encoding="utf-8") as file:
        file.write(version_string)

    print("Generated solaredge2mqtt/_version.py")
    print(f"Version: {versions['version']}")

if __name__ == "__main__":
    generate_static_version_file()
