from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "mysql+pymysql://root:@localhost/inventory", # this is upmost security
    future=True,
    echo=False,
    pool_pre_ping=True, # run SELECT 1
    pool_recycle=3600 # establish new connection every hour
)

"""

sqlite:///inventory.db # SQLite example

pymysql should work, else install mysqlclient>=2.2,<2.3
mysql+pymysql
mysql+mysqldb://inventory:@localhost/inventory  # MySQL / MariaDB example
│       │          │        │          │
│       │          │        │          └─ database name
│       │          │        └─ host
│       │          └─ user:password (empty)
│       └─ driver (mysqlclient)
└─ SQLAlchemy dialect
"""

SessionLocal = sessionmaker(bind=engine)
