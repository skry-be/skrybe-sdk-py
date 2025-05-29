from setuptools import setup, find_packages

setup(
    name="skrybe-sdk",
    version="0.1.0",
    description="Django-compatible SDK for Skrybe API.",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "requests>=2.0.0"
    ],
    python_requires=">=3.7",
    include_package_data=True,
    url="https://dashboard.skry.be",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
