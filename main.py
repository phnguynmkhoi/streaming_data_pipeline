from sqlalchemy import create_engine, Column, Integer, String, UUID, Float
from sqlalchemy.orm import declarative_base, sessionmaker

from datetime import datetime
from dotenv import load_dotenv
import random
import os

load_dotenv()

def mysql_session()

def insert_transaction(session, database, collection_name, transaction):
    db = client[db_name]
    collection = db[collection_name]
    collection.insert_one(transaction)

def main():
    user = 
    connection_string = 

    Base = declarative_base()