from sqlalchemy import BigInteger, Column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Trainer(Base):
    __tablename__ = "trainers"

    id = Column(BigInteger, primary_key=True)
