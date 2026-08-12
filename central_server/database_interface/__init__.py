import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

url = os.getenv("DATABASE_URL")
if not url:
    url = URL.create(
        drivername="postgresql",
        username="postgres",
        password="postgres",
        host="localhost",
        database="BlackJack"
    )
engine = create_engine(url)
SessionLocal = sessionmaker(bind=engine)
