"""Package setup for scs_cn_runoff."""
from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", encoding="utf-8") as fh:
    requirements = [
        line.strip()
        for line in fh
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="scs_cn_runoff",
    version="1.0.0",
    author="Hydrology Team",
    description="Production-ready SCS-CN runoff estimation for watershed analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests*", "docs*"]),
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "geo": ["geopandas>=0.13", "shapely>=2.0", "pyproj>=3.5"],
        "dev": ["pytest>=7.4", "pytest-cov>=4.1", "black", "ruff", "mypy"],
    },
    entry_points={
        "console_scripts": [
            "scs-cn=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Hydrology",
    ],
)
