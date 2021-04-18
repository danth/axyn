FROM python:3.7

WORKDIR /usr/src/axyn
# Data volume should be mounted here
ENV HOME=/axyn

# Install dependencies
COPY setup.py README.md ./
COPY .git/ .git/
RUN pip install --no-cache-dir -e .

# Download NLP model
RUN python -m spacy download en_core_web_md

# Copy code
COPY . .

CMD [ "axyn" ]
