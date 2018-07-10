import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Check for environment variable, prioritize URL from secrets.py
if not os.getenv("DATABASE_URL"):
    try:
        from secrets import DATABASE_URL
    except ImportError:
        raise ImportError("DATABASE_URL is not set and no secrets.py found")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

db.execute('CREATE TABLE books (isbn VARCHAR PRIMARY KEY, title VARCHAR, author VARCHAR, year INTEGER)')
db.commit()

with open('books.csv', 'r') as f:
    reader = csv.reader(f, delimiter=',')
    next(reader, None)
    for isbn, title, author, year in reader:
        db.execute('INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)',
                  {'isbn': isbn, 'title': title, 'author': author, 'year': year})

db.commit()

print('import successful')