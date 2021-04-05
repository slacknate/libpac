from setuptools import setup, find_packages


setup(

    name="libpac",
    version="0.0.1",
    url="https://github.com/slacknate/libpac",
    description="A library for extracting PAC file sprite data.",
    packages=find_packages(include=["libpac", "libpac.*"]),
)
