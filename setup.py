#!/usr/bin/python
from setuptools import setup, find_packages

setup(
    name='trollop',
    version='0.0.17',
    author='Brent Tubbs',
    author_email='brent.tubbs@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests>=1.2.0',
        'six>=1.10.0',
        'isodate>=0.5.4',
    ],
    url='http://bitbucket.org/btubbs/trollop',
    description='A Python library for working with the Trello api.',
    long_description=open('README.rst').read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
    ],
)
