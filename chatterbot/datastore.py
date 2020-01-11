import os


def get_path(file):
    """Return the path of the given file within Chatterbot's data directory."""

    # Find path of data directory
    folder = os.path.expanduser('~/chatterbot')
    # Create directory if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, file)
