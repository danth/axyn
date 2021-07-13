import logging
import os

from axyn.client import AxynClient


def launch():
    """
    Start Axyn.

    The login token is taken from the environment variable ``DISCORD_TOKEN``.
    """

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("axyn").setLevel(logging.DEBUG)

    client = AxynClient()
    client.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    launch()
