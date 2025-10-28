#!/usr/bin/env python3
"""
Setup script for elvsim (Elevator Simulation System)
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="elvsim",
    version="0.1.0",
    author="CahootsJP",
    description="A comprehensive elevator simulation system with group control and visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CahootsJP/elvsim-simple",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "examples"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "simpy>=4.0.0",
        "numpy>=1.20.0",
        "matplotlib>=3.3.0",
        "sympy>=1.9",
        "flask>=2.0.0",
        "flask-cors>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "sphinx>=4.5.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "elvsim-viz=visualizer.server.http_server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "visualizer": ["static/*"],
    },
)

