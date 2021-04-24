from sqlalchemy import BigInteger, Column, Boolean

from axyn.settings import Setting
from axyn.models import Base


def make_model(name, datatype):
    """Create a database model with the given name and datatype."""

    # This dynamically defines a class with the given name
    return type(name, (Base,), {
        "__tablename__": f"setting_{name}",
        "id": Column(BigInteger, primary_key=True),
        "value": Column(datatype),
    })


class Learning(Setting):
    name = "learning"
    datatype = bool
    thing = "whether Axyn will learn messages"
    user_model = make_model("learning_user", Boolean)
    channel_model = make_model("learning_channel", Boolean)
    guild_model = make_model("learning_guild", Boolean)

    def merge_values(self, user_value, channel_value, guild_value):
        # If the channel or guild has explicitly disabled learning, honour that
        if channel_value is False or guild_value is False:
            return False

        # Otherwise, use the user's preference
        return bool(user_value)


ALL_SETTINGS = [
    Learning
]
