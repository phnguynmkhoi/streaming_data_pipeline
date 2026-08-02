from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker

from models import Base


def create_session(host, port, username, password, database):
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    engine = create_engine(connection_string)

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    return session


def bulk_insert(session, data_class, data):
    if not data:
        return
    try:
        session.execute(insert(data_class), data)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error bulk inserting {data_class.__tablename__}:", e)
