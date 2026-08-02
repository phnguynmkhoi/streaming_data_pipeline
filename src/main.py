import random
import uuid
from datetime import datetime

import faker
from dotenv import load_dotenv
import os

from data_generator import DataGenerator
from db import create_session, bulk_insert
from models import User, Product, Payment, Shipping, Transaction

fake = faker.Faker()

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
bulk_insert(postgres_session, User, users)

for i in range(PRODUCT_LENGTH):
    product = data_generator.generate_product()
    product["last_modified_ts"] = str(datetime.now())
    products.append(product)
bulk_insert(postgres_session, Product, products)

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

bulk_insert(postgres_session, Payment, payments)

TRANSACTION_LENGTH = 100000
transactions = []
shippings = []
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

    transactions.append(transaction)
    shippings.append(shipping)

bulk_insert(postgres_session, Shipping, shippings)
bulk_insert(postgres_session, Transaction, transactions)
postgres_session.close()
