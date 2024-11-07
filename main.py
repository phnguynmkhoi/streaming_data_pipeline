from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_generator import generate_transaction

from dotenv import load_dotenv
import os

from sqlalchemy import Column, VARCHAR, Float, TIMESTAMP, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"    

    transaction_id = Column(UUID(), primary_key=True, nullable=False)
    user_id = Column(UUID(),nullable=False)
    timestamp = Column(TIMESTAMP(True))
    amount = Column(Float())
    currency = Column(VARCHAR(200))
    city = Column(VARCHAR(200))
    country = Column(VARCHAR(200))
    merchant_name = Column(VARCHAR(200))
    payment_method = Column(VARCHAR(200))
    ip_address = Column(VARCHAR(200))
    voucher_code = Column(VARCHAR(200))
    affiliate_id = Column(UUID(),nullable=False)

def create_session(host, port, username, password, database):
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    print(connection_string)
    engine = create_engine(connection_string)

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    return session

def insert_transaction(session, transaction):
    
    try:
        new_transaction = Transaction(**transaction)
        session.add(new_transaction)
        session.commit()
        print("Transaction committed successfully")
    except Exception as e:
        session.rollback()
        print("Error inserting transaction:", e)

if __name__=="__main__":
    load_dotenv()

    username = os.getenv("POSTGRES_USERNAME")
    password = os.getenv("POSTGRES_PASSWORD")
    host = "localhost"
    port = 5432
    db_name = "cdc_db"

    postgres_session = create_session(host,port,username,password,db_name)

    for i in range(50):
        transaction = generate_transaction()
        insert_transaction(postgres_session,transaction)

    postgres_session.close()
