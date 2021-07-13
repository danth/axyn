from os import path

from setuptools import find_packages, setup

# Read long description from README.md
here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.md"), encoding="utf-8") as readme:
    long_description = readme.read()


setup(
    name="axyn",
    use_scm_version=True,
    description="A Discord chatbot built using Flipgenic",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Daniel Thwaites",
    author_email="danthwaites30@btinternet.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="Discord bot chatbot",
    url="https://github.com/danth/axyn",
    project_urls={
        "Bug Reports": "https://github.com/danth/axyn/issues",
        "Source": "https://github.com/danth/axyn",
    },
    packages=find_packages(),
    python_requires=">=3.6,<4",
    setup_requires=["setuptools_scm"],
    install_requires=[
        "flipgenic >=2.2.0,<3",
        "spacy >=3,<4",
        "discord.py >=1.2.5,<2",
        "discord-py-slash-command >2,<3",
        "discordhealthcheck >=0.0.7,<1",
        "sqlalchemy >=1,<2",
        "emoji >=0.5,<1",
        "numpy >=1.20,<2",
        "logdecorator >=2.2,<3",
    ],
    entry_points={
        "console_scripts": [
            "axyn=axyn.__main__:launch",
        ],
    },
)
