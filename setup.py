#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup configuration for gakr-ddgs package."""

from setuptools import setup

setup(
    name="gakr-ddgs",
    version="1.0.0",
    author="Ashok-gakr",
    description="Enterprise-grade DuckDuckGo search toolkit with content extraction, cleaning, and structured JSON output",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Ashok-gakr/gakr-ddgs",
    packages=["gakr_ddgs"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "duckduckgo-search>=3.9.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "trafilatura>=1.6.0",
        "justext>=3.0.0",
        "boilerpy3>=1.0.0",
        "rich>=13.0.0",
        "urllib3>=1.26.0",
    ],
    entry_points={
        "console_scripts": [
            "gakr-ddgs=gakr_ddgs.cli:main",
        ],
    },
)
