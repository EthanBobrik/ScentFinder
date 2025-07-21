from sqlalchemy import Column, ForeignKey, Integer, Table, String
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

cologne_notes = Table(
    "cologne_notes", Base.metadata,
    Column("cologne_id", Integer, ForeignKey("cologne.id")),
    Column("note_id", Integer, ForeignKey("notes.id"))
)

class Cologne(Base):
    __tablename__ = "colognes"

    id = Column(Integer, primary_key=True)
    name = Column(String,unique=True)
    brand = Column(String)
    launch_year = Column(Integer)
    url = Column(String)

    notes = relationship("Note", secondary=cologne_notes,back_populates="colognes")

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    name = Column(String,unique=True)
    group = Column(String)
    description = Column(String)
    url = Column(String)

    colognes = relationship("Cologne", secondary=cologne_notes,back_populates="notes")