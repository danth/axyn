import logging

from logdecorator import log_on_end


@log_on_end(logging.DEBUG, 'Preprocessed "{content}" to "{result}"')
def preprocess(client, content: str):
    """Return a cleaned-up version of the given message contents."""

    # Strip off leading @Axyn if it exists
    axyn = client.user.mention
    if content.startswith(axyn):
        content = content[len(axyn) :]

    # Remove leading/trailing whitespace
    content = content.strip()

    return content
