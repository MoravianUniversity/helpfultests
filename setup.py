import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="helpfultests",
    version="0.0.9",
    author="Jeffrey Bush",
    author_email="bushj@moravian.edu",
    description="More elaborative test messages for unittest package",
    long_description=read('README.md'),
    license="BSD",
    packages=['helpfultests'],
    install_requires=["astor>=0.7.0"],
    python_requires='~=3.7',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Software Development :: Testing :: Unit",
        "Topic :: Education :: Testing",
        "License :: OSI Approved :: BSD License",
    ],
)