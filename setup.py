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
        "sqlalchemy >=1.3,<4",
        "flipgenic >=0.3.1,<1",
        "cairosvg >=2,<3",
        "discord.py >=1.2.5,<2",
        "emoji >=0.5,<1",
        "chickennuggets >=1,<2",
    ],
    entry_points={"console_scripts": ["axyn=axyn.__main__:launch",],},
)
