from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.readlines()
requirements = [i.replace('\n', '') for i in requirements]

version = '0.1.0'

setup(name = 'txsc',
    version = version,
    description = 'Transaction script compiler.',
    author = 'Tyler Willis',
    author_email = 'kefkius@maza.club',
    url = 'https://github.com/kefkius/txsc',
    packages = find_packages(),
    install_requires = requirements,
    entry_points = {
        'console_scripts': [
            'txsc = txsc.compiler:main',
        ],
        'txsc.language': [
            'ASM = txsc.asm.asm_language:get_lang',
            'BTC = txsc.btcscript:get_lang',
            'TxScript = txsc.txscript.txscript_language:get_lang',
        ]
    },
    test_suite = 'txsc.tests'
)
