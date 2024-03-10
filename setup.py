import setuptools

import versioneer

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.readlines()


packages = setuptools.find_packages(exclude=["tests"])

setuptools.setup(
    name="solaredge2mqtt",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Read data from SolarEdge Inverter and publish it to MQTT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/deroetzi/solaredge2mqtt",
    author="Johannes Ott",
    author_email="info@johannes-ott.net",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="smart home",
    packages=packages,
    include_package_data=True,
    python_requires=">=3.10, <4",
    install_requires=[req for req in requirements if not req.startswith("#")],
    entry_points={"console_scripts": ["solaredge2mqtt=solaredge2mqtt.service:run"]},
    project_urls={"Bug Reports": "https://github.com/deroetzi/solaredge2mqtt/issues"},
)
