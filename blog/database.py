from sqlalchemy import create_engine

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import sessionmaker

from urllib.parse import quote_plus



PG_USER = "postgres"
PG_PASS = quote_plus("Test@123")
PG_HOST = "localhost"
PG_PORT = "5432"
PG_DB   = "blogdb"



SQLALCHEMY_DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)


Sessionlocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()

