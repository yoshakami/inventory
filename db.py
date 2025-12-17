from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "sqlite:///inventory.db",
    future=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)
