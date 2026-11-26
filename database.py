
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models import Base


db_url = "mysql+pymysql://root:anagha@localhost:3306/docuextract"


engine = create_engine(db_url)


SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)



def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
