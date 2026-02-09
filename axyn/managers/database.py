from __future__ import annotations
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from axyn.database import (
    SCHEMA_VERSION,
    BaseRecord,
    IndexRecord,
    SchemaVersionRecord,
    get_path,
)
from axyn.managers import Manager
from datetime import datetime
from enum import Enum
from shutil import rmtree
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as EnumType,
    delete,
    desc,
    select,
    table,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.event import listen
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from sqlalchemy import Connection
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.pool import ConnectionPoolEntry

class DatabaseManager(Manager):
    """Holds a connection to the database and controls database migrations."""

    def __init__(self, client: AxynClient):
        super().__init__(client)

        uri = "sqlite+aiosqlite:///" + get_path("database.sqlite3")

        engine = create_async_engine(uri)

        def on_connect(
            dbapi_connection: DBAPIConnection,
            connection_record: ConnectionPoolEntry,
        ):
            dbapi_connection.isolation_level = None

            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

        listen(engine.sync_engine, "connect", on_connect)

        def on_begin(connection: Connection):
            options = connection.get_execution_options()
            begin = "BEGIN " + options["transaction_mode"]
            connection.exec_driver_sql(begin)

            # This only applies to the current transaction, so cannot be with
            # the other settings above.
            connection.exec_driver_sql("PRAGMA defer_foreign_keys=ON")

        listen(engine.sync_engine, "begin", on_begin)

        read_engine = engine.execution_options(transaction_mode="DEFERRED")
        write_engine = engine.execution_options(transaction_mode="IMMEDIATE")

        self.read_session = async_sessionmaker(bind=read_engine)
        self.write_session = async_sessionmaker(bind=write_engine)

    async def setup_hook(self):
        """Ensure the database is following the current schema."""

        async with self.write_session() as session:
            try:
                version = await session.scalar(
                    select(SchemaVersionRecord.schema_version)
                    .order_by(desc(SchemaVersionRecord.applied_at))
                    .limit(1)
                )
            except OperationalError:
                version = None

            if version is None:
                await self._create_new(session)
            else:
                await self._migrate(session, version)

            await session.commit()

    async def _create_new(self, session: AsyncSession):
        """Create a new database from a blank slate."""

        connection = await session.connection()
        await connection.run_sync(BaseRecord.metadata.create_all)

        session.add(SchemaVersionRecord(
            schema_version=SCHEMA_VERSION,
            applied_at=datetime.now(),
        ))

    async def _migrate(self, session: AsyncSession, version: int):
        """
        Migrate an existing database starting from the given version.

        Throws an exception if the current version is less than zero or greater
        than the current version.
        """

        if version == SCHEMA_VERSION:
            return

        if version < 0:
            raise Exception(f"database schema version {version} is not valid")

        if version > SCHEMA_VERSION:
            raise Exception(f"database schema version {version} is not supported ({SCHEMA_VERSION} is the newest supported)")

        connection = await session.connection()
        await connection.run_sync(self._migrate_operations, version)

        session.add(SchemaVersionRecord(
          schema_version=SCHEMA_VERSION,
          applied_at=datetime.now(),
        ))

    def _migrate_operations(self, connection: Connection, version: int):
        """Migrate an existing database starting from the given version."""

        context = MigrationContext.configure(connection)
        operations = Operations(context)

        if version < 4:
            with operations.batch_alter_table("message") as batch:
                batch.add_column(Column(
                    "deleted_at",
                    DateTime(),
                    nullable=True,
                ))

        if version < 8:
            # Change from {NO, YES} to {NO, WITH_PRIVACY, WITHOUT_PRIVACY}.
            # To do this, we need to temporarily use a type that contains all
            # four options, so that we can convert YES into WITH_PRIVACY while
            # both are valid.

            class Old(Enum):
                NO = 0
                YES = 1

            class Transition(Enum):
                NO = 0
                YES = 1
                WITH_PRIVACY = 2
                WITHOUT_PRIVACY = 3

            class New(Enum):
                NO = 0
                WITH_PRIVACY = 1
                WITHOUT_PRIVACY = 2

            with operations.batch_alter_table("consent_response") as batch:
                batch.alter_column(
                    "response",
                    existing_type=EnumType(Old),
                    existing_nullable=False,
                    type_=EnumType(Transition),
                    nullable=False,
                )

            transition_table = table(
                "consent_response",
                Column("response", EnumType(Transition), nullable=False),
                # Other columns omitted because they are not used below
            )

            operations.execute(
                transition_table
                .update()
                .where(transition_table.c.response == Transition.YES)
                .values(response=Transition.WITH_PRIVACY)
            )

            with operations.batch_alter_table("consent_response") as batch:
                batch.alter_column(
                    "response",
                    existing_type=EnumType(Transition),
                    existing_nullable=False,
                    type_=EnumType(New),
                    nullable=False,
                )

        if version < 10:
            batch_context = operations.batch_alter_table(
                "message",
                naming_convention={
                    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
                },
            )

            with batch_context as batch:
                batch.drop_constraint(
                    "fk_message_reference_id_message",
                    type_="foreignkey",
                )

        if version < 11:
            with operations.batch_alter_table("message") as batch:
                batch.add_column(Column("ephemeral", Boolean(), nullable=True))

        if version < 14:
            # This only needs to happen once, even if we skipped over multiple
            # versions that would reset the index.
            self._reset_index(operations)

    def _reset_index(self, operations: Operations):
        """
        Reset the index.

        This clears the index table in the database, and also removes the
        corresponding file on disk.

        This must be called before the ``IndexManager`` is loaded to avoid
        causing undefined behaviour.
        """

        operations.execute(delete(IndexRecord))

        rmtree(get_path("index"))

