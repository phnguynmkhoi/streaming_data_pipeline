from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_generator import generate_transaction

from dotenv import load_dotenv
import os

from sqlalchemy import Column, VARCHAR, Float, TIMESTAMP, UUID,CHAR, DATE, INTEGER
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "ecommerce_transactions"    

    transaction_id = Column(UUID(), primary_key=True, nullable=False)
    name = Column(VARCHAR(50),nullable=False)
    sex = Column(CHAR(1))
    address = Column(VARCHAR(100))
    phone_number = Column(VARCHAR(50))
    birthdate = Column(TIMESTAMP)
    email = Column(VARCHAR(50))
    job = Column(VARCHAR(50))
    product_name = Column(VARCHAR(50))
    category = Column(VARCHAR(50))
    unit_price = Column(Float)
    quantity = Column(INTEGER)
    merchant_name = Column(VARCHAR(50))
    payment_method = Column(VARCHAR(50))
    discount = Column(INTEGER)
    shipping_address = Column(VARCHAR(100))
    shipping_cost = Column(Float)
    total = Column(Float)
    currency = Column(VARCHAR(50))
    created_at = Column(TIMESTAMP)

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
    db_name = "transactions_db"

    postgres_session = create_session(host,port,username,password,db_name)

    for i in range(5):
        transaction = generate_transaction()
        insert_transaction(postgres_session,transaction)

    postgres_session.close()
