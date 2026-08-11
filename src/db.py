from sqlalchemy import create_engine, insert, update, delete
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


def update_row(session, data_class, pk_column, pk_value, values):
    try:
        stmt = update(data_class).where(getattr(data_class, pk_column) == pk_value).values(**values)
        session.execute(stmt)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error updating {data_class.__tablename__}:", e)


def delete_row(session, data_class, pk_column, pk_value):
    try:
        stmt = delete(data_class).where(getattr(data_class, pk_column) == pk_value)
        session.execute(stmt)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error deleting {data_class.__tablename__}:", e)
