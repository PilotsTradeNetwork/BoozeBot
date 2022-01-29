import io
import os
from pathlib import Path
from importlib import util

from setuptools import setup

NAMESPACE = 'ptn'
COMPONENT = 'boozebot'

here = Path().absolute()

# Bunch of things to allow us to dynamically load the metadata file in order to read the version number.
# This is really overkill but it is better code than opening, streaming and parsing the file ourselves.

metadata_name = f'{NAMESPACE}.{COMPONENT}._metadata'
spec = util.spec_from_file_location(metadata_name, os.path.join(here, NAMESPACE, COMPONENT, '_metadata.py'))
metadata = util.module_from_spec(spec)
spec.loader.exec_module(metadata)

# load up the description field
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name=f'{NAMESPACE}.{COMPONENT}',
    version=metadata.__version__,
    description='Pilots Trade Network Booze Bot',
    long_description=long_description,
    author='Graeme Cruickshank',
    url='',
    install_requires=[
        'discord.py',
        'discord-py-slash-command',
        'google-api-python-client',
        'gspread',
        'oauth2client',
        'requests',
        'python-dotenv'
    ],
    entry_points={
        'console_scripts': [
            'booze=ptn.boozebot.booze:run',
        ],
    },
    license='MIT',
    keyworkd='PTN',
    project_urls={
        "Source": "https://github.com/PilotsTradeNetwork/BoozeBot",
    },
    python_required='>=3.9',
)
