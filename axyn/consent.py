import logging
from contextlib import contextmanager

from discord_slash import SlashCommand
from discord_slash.utils.manage_components import create_button, create_actionrow
from discord_slash.model import ButtonStyle
import sqlalchemy
from sqlalchemy import BigInteger, Column, Boolean
from sqlalchemy.ext.declarative import declarative_base

from axyn.datastore import get_path


# Set up logging
logger = logging.getLogger(__name__)


Base = declarative_base()

class UserConsent(Base):
    __tablename__ = "consent"
    user_id = Column(BigInteger, primary_key=True)
    consented = Column(Boolean, primary_key=True)


def connect_to_database():
    """Connect to the SQLite database which stores consent data."""

    logger.info("Opening SQLite database")
    database_url = "sqlite:///" + get_path("consent.sqlite3")
    engine = sqlalchemy.create_engine(database_url)

    logger.info("Creating tables")
    Base.metadata.create_all(engine)

    Session = sqlalchemy.orm.sessionmaker(bind=engine)

    @contextmanager
    def database_session():
        session = Session()
        session.begin()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    return database_session


def format_button_id(user, consented):
    """Create a string which identifies a consent button."""

    choice = "yes" if consented else "no"
    return f"{user.id}-{choice}"

def unpack_button_id(button_id):
    """Extract the user and choice from a consent button identifier."""

    user_id_string, choice = button_id.split("-")
    return int(user_id_string), choice == "yes"


def setup_consent(client):
    """Add a slash command which toggles learning on a per-user basis."""

    slash = SlashCommand(client, sync_commands=True)
    database_session = connect_to_database()

    @slash.slash(name="consent", description="Change whether Axyn learns your messages.")
    async def consent(ctx):
        logger.info("Sending consent menu to %i", ctx.author.id)

        await ctx.send("Can I learn your messages?", components=[create_actionrow(
            create_button(
                style=ButtonStyle.green,
                label="Yes",
                custom_id=format_button_id(ctx.author, True),
            ),
            create_button(
                style=ButtonStyle.red,
                label="No",
                custom_id=format_button_id(ctx.author, False),
            ),
        )])

    @client.event
    async def on_component(ctx):
        await ctx.defer(edit_origin=True)

        user_id, consented = unpack_button_id(ctx.custom_id)
        with database_session() as session:
            session.merge(UserConsent(user_id=user_id, consented=consented))

        logger.info("User %i changed their consent setting to %s", user_id, consented)

        if consented:
            await ctx.edit_origin(content="I'll learn messages you send from now on. Thanks!", components=[])
        else:
            await ctx.edit_origin(content="No problem, I won't learn from you.", components=[])


def get_consent_setting(user):
    """Return whether a user has allowed their messages to be learned."""

    with database_session() as session:
        setting = session.query(UserConsent).where(UserConsent.user_id == user.id).one_or_none()
        if setting is None:
            return False
        else:
            return setting.consented
