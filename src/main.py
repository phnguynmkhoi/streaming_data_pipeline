from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
import random

from data_generator import DataGenerator

from dotenv import load_dotenv
import os

from sqlalchemy import Column, VARCHAR, Float, TIMESTAMP, UUID,CHAR, INTEGER
from sqlalchemy.orm import declarative_base

import faker

from datetime import datetime

fake = faker.Faker()

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(),primary_key=True)
    full_name = Column(VARCHAR(100))
    sex = Column(CHAR(1))
    address = Column(VARCHAR(100))
    phone_number = Column(VARCHAR(100))
    birthdate = Column(VARCHAR(100))
    email = Column(VARCHAR(100))
    job = Column(VARCHAR(100))
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))

class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(),primary_key=True)
    product_name = Column(VARCHAR(100))
    category = Column(VARCHAR(100))
    unit_price = Column(Float)
    merchant_name = Column(VARCHAR(100))
    rating = Column(Float)
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(UUID(),primary_key=True)
    payment_method = Column(VARCHAR(100))
    currency = Column(VARCHAR(10))
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))

class Shipping(Base):
    __tablename__ = "shippings"

    shipping_id = Column(UUID(), primary_key=True)
    shipping_address = Column(VARCHAR(200))
    shipping_cost = Column(Float)
    shipping_status = Column(VARCHAR(50))
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))

class Transaction(Base):
    __tablename__ = "transactions"    

    transaction_id = Column(UUID(), primary_key=True, nullable=False)
    user_id = Column(UUID())
    product_id = Column(UUID())
    payment_id = Column(UUID())
    shipping_id = Column(UUID())
    quantity = Column(INTEGER)
    discount = Column(INTEGER)
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))

def create_session(host, port, username, password, database):
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    print(connection_string)
    engine = create_engine(connection_string)

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    return session

def insert_data(session, data_class, data):
    
    try:
        new_data = data_class(**data)
        session.add(new_data)
        session.commit()
        # print("Transaction committed successfully")
    except Exception as e:
        session.rollback()
        print("Error inserting transaction:", e)

load_dotenv()

username = os.getenv("POSTGRES_USERNAME")
password = os.getenv("POSTGRES_PASSWORD")
host = "localhost"
port = 5432
db_name = "transactions_db"

postgres_session = create_session(host,port,username,password,db_name)

data_generator = DataGenerator()
users = []
products = []
payments = []

USER_LENGTH = 100
PRODUCT_LENGTH = 50

for i in range(USER_LENGTH):
    user = data_generator.generate_user()
    user["last_modified_ts"] = str(datetime.now())
    users.append(user)
    insert_data(postgres_session, User, user)

for i in range(PRODUCT_LENGTH):
    product = data_generator.generate_product()
    product["last_modified_ts"] = str(datetime.now())
    products.append(product)
    insert_data(postgres_session, Product, product)

PAYMENT_LENGTH = 30
for i in range(PAYMENT_LENGTH):
    payment = {}
    payment["payment_method"] = random.choice(['Visa', 'Mastercard', 'Credit Card', 'Debit Card','Paypal'])
    payment["currency"] = fake.currency_code()
    payment["status"] = "INSERT"
    payment["last_modified_ts"] = str(datetime.now())
    if payment not in payments:
        payments.append(payment)

for i in range(len(payments)):
    payments[i]["payment_id"] = str(uuid.uuid4())

    insert_data(postgres_session, Payment, payments[i])

TRANSACTION_LENGTH = 1000
for i in range(TRANSACTION_LENGTH):
    transaction = {}
    shipping = {}
    user = users[random.randint(0,USER_LENGTH-1)]
    product_id = products[random.randint(0,PRODUCT_LENGTH-1)]["product_id"]
    payment_id = payments[random.randint(0,len(payments)-1)]["payment_id"]
    transaction = {}
    transaction["transaction_id"] = str(uuid.uuid4())
    transaction["user_id"] = user["user_id"]
    transaction["product_id"] = product_id
    transaction["payment_id"] = payment_id
    transaction["quantity"] = random.randint(1,10)
    transaction["discount"] = random.choices([15,10,5,0],[0.05,0.05,0.1,0.8])[0]
    transaction["last_modified_ts"] = str(datetime.now())
    transaction["status"] = "INSERT"
    
    shipping_id = str(uuid.uuid4())
    transaction["shipping_id"] = shipping_id

    shipping["shipping_id"] = shipping_id
    shipping["shipping_address"] = random.choices([user["address"],fake.address()],[0.9,0.1])[0]
    shipping["shipping_cost"] = round(random.uniform(0,30),2)
    shipping["shipping_status"] = random.choices(["In-Transit","Delay","Shipped","Out-for-delivery","Delivered"])[0]
    shipping["last_modified_ts"] = str(datetime.now())
    shipping["status"] = "INSERT"

    insert_data(postgres_session, Transaction, transaction)
    insert_data(postgres_session, Shipping, shipping)
postgres_session.close()
