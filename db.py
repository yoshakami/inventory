from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "mysql+mysqldb://root:@localhost/inventory", # this is upmost security
    future=True,
    echo=False,
)

"""
sqlite:///inventory.db # SQLite example

mysql+mysqldb://inventory:@localhost/inventory  # MySQL / MariaDB example
│       │          │        │          │
│       │          │        │          └─ database name
│       │          │        └─ host
│       │          └─ user:password (empty)
│       └─ driver (mysqlclient)
└─ SQLAlchemy dialect
"""

SessionLocal = sessionmaker(bind=engine)
