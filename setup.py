import os
from setuptools import setup, find_packages

f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
readme = f.read()
f.close()

setup(
    name='irckit',
    version="0.1.1",
    description='tinkering with a made-from-scratch irc library in python',
    long_description=readme,
    author='Charles Leifer',
    author_email='coleifer@gmail.com',
    url='http://github.com/coleifer/irc/',
    packages=find_packages(),
    py_modules=['irc'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
)
