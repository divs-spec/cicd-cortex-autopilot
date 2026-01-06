from setuptools import setup, find_packages

setup(
    name="aeia",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "PyGithub>=2.1.1",
        "anthropic>=0.18.1",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.1",
        "click>=8.1.7",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "aeia=phase1.cli:main",
        ],
    },
    python_requires=">=3.9",
)
