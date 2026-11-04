from setuptools import setup, find_packages

setup(
    name="certis-dt",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.22.0",
    ],
    entry_points={
        "console_scripts": [
            "certis=certis_dt.cli.main:main",
        ],
    },
)
