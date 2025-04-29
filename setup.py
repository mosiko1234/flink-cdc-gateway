#!/usr/bin/env python

from setuptools import setup, find_packages
import os

# Read version from __init__.py
with open(os.path.join("cdc_gateway", "__init__.py"), "r") as f:
    for line in f.readlines():
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"\'')
            break

# Read long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Define requirements directly - don't rely on requirements.txt
requirements = [
    "flask==2.0.1",
    "flask-restful==0.3.9",
    "werkzeug==2.0.2",
    "requests==2.28.2",
    "pyyaml>=6.0",
    "jsonschema>=4.0.0",
    "kafka-python>=2.0.2",
    "prometheus-client>=0.11.0",
    "python-dotenv>=0.19.0",
    "gunicorn>=20.1.0",
    "psutil>=5.9.0",
]

setup(
    name="flink-cdc-gateway",
    version=version,
    author="Moshe Eliya",
    author_email="mosiko1234@gmail.com",
    description="Change Data Capture Gateway for Apache Flink",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mosiko1234/flink-cdc-gateway",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "cdc-gateway=cdc_gateway.app:main",
            "cdc-gateway-admin=cdc_gateway.admin:main",
            "cdc-gateway-monitor=cdc_gateway.monitor:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)