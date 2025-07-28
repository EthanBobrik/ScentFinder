from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base

#Sqlite db
engine = create_engine("sqlite:///../database/database.db", echo=True)
Base.metadata.create_all(engine)

#create session
Session = sessionmaker(bind=engine)
session = Session()