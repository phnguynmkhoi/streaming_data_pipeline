import faker
from pymongo import MongoClient
from datetime import datetime
import random

fake = faker.Faker()

def generate_transaction():
    user = fake.simple_profile()

    return {
        "transactionId": fake.uuid4(),
        "userId": user['username'],
        "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
        "amount": round(random.uniform(10, 1000), 2),
        "currency": random.choice(['USD', 'EUR', 'GBP']),
        "city": fake.city(),
        "country": fake.country(),
        "merchantName": fake.company(),
        "paymentMethod": random.choice(['Visa', 'Mastercard', 'Credit Card', 'Debit Card','Paypal']),
        "ipAddress": fake.ipv4(),
        "voucherCode": random.choice(["","DISCOUNT10","",""]),
        'affiliateId': fake.uuid4()
    }

def mongodb_connection(hostname:str,username: str, password: str):
    client = MongoClient(f'mongodb://{username}:{password}@{hostname}', authSource='admin')
    return client

def insert_transaction(client, db_name, collection_name, transaction):
    db = client[db_name]
    collection = db[collection_name]
    collection.insert_one(transaction)

def main():
    client = mongodb_connection('localhost:27017', 'admin', 'admin')
    db_name = 'cdc'
    collection_name = 'transactions'