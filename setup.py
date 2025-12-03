from os import path

from setuptools import find_packages, setup

# Read long description from README.md
here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.md"), encoding="utf-8") as readme:
    long_description = readme.read()


setup(
    name="axyn",
    version="8.9.1",
    description="A Discord chatbot using traditional algorithms",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Daniel Thwaites",
    author_email="danthwaites30@btinternet.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
    ],
    keywords="Discord bot chatbot",
    url="https://github.com/danth/axyn",
    project_urls={
        "Bug Reports": "https://github.com/danth/axyn/issues",
        "Source": "https://github.com/danth/axyn",
    },
    packages=find_packages(),
    python_requires=">=3.13,<4", # Keep in sync with pyproject.toml
    install_requires=[
        "alembic >=1,<2",
        "discord.py >=2,<3",
        "discordhealthcheck >=0.0.7,<1",
        "fastembed >=0.7,<1",
        "ngt >=2,<3",
        "sqlalchemy[aiosqlite] >=2,<3",
    ],
    extras_require={
        "build": [
            "build >=1,<2",
        ],
        "test": [
            "coverage >=7,<8",
            "pytest >=8,<9",
            "pytest-asyncio >=1,<2",
        ],
    },
    entry_points={
        "console_scripts": [
            "axyn=axyn.__main__:launch",
        ],
    },
)
