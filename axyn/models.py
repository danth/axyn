from sqlalchemy import Column, Integer, BigInteger, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Statement(Base):
    __tablename__ = 'statements'

    id = Column(Integer, primary_key=True)
    ngt_id = Column(Integer)
    text = Column(String)


class Reaction(Base):
    __tablename__ = 'reactions'

    id = Column(Integer, primary_key=True)
    ngt_id = Column(Integer)
    emoji = Column(String(1))


class Trainer(Base):
    __tablename__ = 'trainers'

    id = Column(BigInteger, primary_key=True)
