from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///movies.db", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    genre = Column(String, default="Drama")
    year = Column(String, default="2024")
    country = Column(String, default="AQSH")
    language = Column(String, default="O'zbek")
    quality = Column(String, default="1080p")
    duration = Column(String, default="1:30")
    file_id = Column(String, nullable=False)
    imdb = Column(Float, default=0.0)
    views = Column(Integer, default=0)
    total_rating = Column(Integer, default=0)
    rating_count = Column(Integer, default=0)

class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    movie_id = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)

class SavedMovie(Base):
    __tablename__ = "saved_movies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    movie_id = Column(Integer, nullable=False)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_username = Column(String, unique=True, nullable=False)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False)

class ChannelJoinRequest(Base):
    __tablename__ = "channel_join_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)