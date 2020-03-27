from setuptools import setup, find_packages
from os import path


# Read long description from README.md
here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as readme:
    long_description = readme.read()


setup(
    name='axyn',
    use_scm_version=True,

    description='Discord interface to https://github.com/gunthercox/ChatterBot with additional features',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Daniel Thwaites',
    author_email='danthwaites30@btinternet.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='Discord bot chatbot chatterbot',

    url='https://github.com/AlphaMycelium/axyn',
    project_urls={
        'Bug Reports': 'https://github.com/AlphaMycelium/axyn/issues',
        'Source': 'https://github.com/AlphaMycelium/axyn',
    },

    packages=find_packages(),
    python_requires='>=3.6,<4',
    setup_requires=['setuptools_scm'],
    install_requires=[
        'chatterbot >=1,<2',
        'chatterbot_corpus',
        'nltk >=3.4,<4',
        'spacy >=2,<3',
        'cairosvg >=2,<3',
        'discord.py >=1.2.5,<2',
        'emoji >=0.5,<1',
        'chickennuggets >=1,<2'
    ]
)
