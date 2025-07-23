from sqlalchemy import Column, ForeignKey, Integer, Table, String, ARRAY, Enum, JSON
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()

class NoteType(enum.Enum):
    TOP = "top"
    MIDDLE = "middle"
    BASE = "base"
    GENERAL = "general"

# Association table with note position information
class CologneNote(Base):
    __tablename__ = "cologne_notes"

    id = Column(Integer, primary_key=True)
    cologne_id = Column(Integer, ForeignKey("colognes.id"), nullable=False)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    note_type = Column(Enum(NoteType), nullable=False)  # TOP, MIDDLE, BASE, or GENERAL

    # Relationships
    cologne = relationship("Cologne", back_populates="notes")
    note = relationship("Note", back_populates="colognes")


class Cologne(Base):
    __tablename__ = "colognes"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    brand = Column(String)
    launch_year = Column(Integer)
    main_accords = Column(JSON,nullable=True)  # List of main accords

    # Keep these for backward compatibility and quick access, but primary data is in relationships
    top_notes = Column(JSON)
    middle_notes = Column(JSON)
    base_notes = Column(JSON)
    general_notes = Column(JSON)

    # Voting data
    longevity_very_weak = Column(Integer)
    longevity_weak = Column(Integer)
    longevity_moderate = Column(Integer)
    longevity_long_lasting = Column(Integer)
    longevity_eternal = Column(Integer)
    sillage_intimate = Column(Integer)
    sillage_moderate = Column(Integer)
    sillage_strong = Column(Integer)
    sillage_enormous = Column(Integer)
    gender_female = Column(Integer)
    gender_more_female = Column(Integer)
    gender_unisex = Column(Integer)
    gender_more_male = Column(Integer)
    gender_male = Column(Integer)
    price_way_overpriced = Column(Integer)
    price_overpriced = Column(Integer)
    price_ok = Column(Integer)
    price_good_value = Column(Integer)
    price_great_value = Column(Integer)

    url = Column(String)

    # Relationships
    cologne_notes = relationship("CologneNote", back_populates="cologne", cascade="all, delete-orphan")

    # Convenience properties to access notes by type
    @property
    def top_notes_objects(self):
        return [cn.note for cn in self.cologne_notes if cn.note_type == NoteType.TOP]

    @property
    def middle_notes_objects(self):
        return [cn.note for cn in self.cologne_notes if cn.note_type == NoteType.MIDDLE]

    @property
    def base_notes_objects(self):
        return [cn.note for cn in self.cologne_notes if cn.note_type == NoteType.BASE]

    @property
    def general_notes_objects(self):
        return [cn.note for cn in self.cologne_notes if cn.note_type == NoteType.GENERAL]


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    group = Column(String)
    url = Column(String)

    # Relationships
    cologne_notes = relationship("CologneNote", back_populates="note")

    # Convenience property to get all colognes that use this note
    @property
    def colognes(self):
        return [cn.cologne for cn in self.cologne_notes]

    # Get colognes by note type
    def get_colognes_by_type(self, note_type: NoteType):
        return [cn.cologne for cn in self.cologne_notes if cn.note_type == note_type]