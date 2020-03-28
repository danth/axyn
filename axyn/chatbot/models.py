from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Statement(Base):
    __tablename__ = 'statements'

    id = Column(Integer, primary_key=True)
    text = Column(String)
    responding_to = Column(String)
    responding_to_bigram = Column(String)


class Reaction(Base):
    __tablename__ = 'reactions'

    id = Column(Integer, primary_key=True)
    emoji = Column(String(1))
    responding_to = Column(String)
    responding_to_bigram = Column(String)
