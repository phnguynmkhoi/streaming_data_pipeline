import argparse
import random
import time
import uuid
from datetime import datetime

import faker
from dotenv import load_dotenv
import os

from data_generator import DataGenerator
from db import create_session, bulk_insert, update_row, delete_row
from models import User, Product, Payment, Shipping, Transaction

fake = faker.Faker()

load_dotenv()

username = os.getenv("POSTGRES_USERNAME")
password = os.getenv("POSTGRES_PASSWORD")
host = "localhost"
port = 5432
db_name = "transactions_db"

data_generator = DataGenerator()

USER_LENGTH = 100
PRODUCT_LENGTH = 50
PAYMENT_LENGTH = 30
TRANSACTION_LENGTH = 100000

SHIPPING_STATUSES = ["In-Transit", "Delay", "Shipped", "Out-for-delivery", "Delivered"]
PAYMENT_METHODS = ['Visa', 'Mastercard', 'Credit Card', 'Debit Card', 'Paypal']

MODEL_PK = {
    "user": (User, "user_id"),
    "product": (Product, "product_id"),
    "payment": (Payment, "payment_id"),
    "shipping": (Shipping, "shipping_id"),
    "transaction": (Transaction, "transaction_id"),
}


def seed_users(session):
    users = []
    for _ in range(USER_LENGTH):
        user = data_generator.generate_user()
        user["last_modified_ts"] = str(datetime.now())
        users.append(user)
    bulk_insert(session, User, users)
    return users


def seed_products(session):
    products = []
    for _ in range(PRODUCT_LENGTH):
        product = data_generator.generate_product()
        product["last_modified_ts"] = str(datetime.now())
        products.append(product)
    bulk_insert(session, Product, products)
    return products


def seed_payments(session):
    payments = []
    for _ in range(PAYMENT_LENGTH):
        payment = {}
        payment["payment_method"] = random.choice(PAYMENT_METHODS)
        payment["currency"] = fake.currency_code()
        payment["status"] = "INSERT"
        payment["last_modified_ts"] = str(datetime.now())
        if payment not in payments:
            payments.append(payment)

    for i in range(len(payments)):
        payments[i]["payment_id"] = str(uuid.uuid4())

    bulk_insert(session, Payment, payments)
    return payments


def generate_transaction_shipping(users, products, payments):
    user = random.choice(users)
    product_id = random.choice(products)["product_id"]
    payment_id = random.choice(payments)["payment_id"]
    shipping_id = str(uuid.uuid4())

    transaction = {
        "transaction_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "product_id": product_id,
        "payment_id": payment_id,
        "shipping_id": shipping_id,
        "quantity": random.randint(1, 10),
        "discount": random.choices([15, 10, 5, 0], [0.05, 0.05, 0.1, 0.8])[0],
        "last_modified_ts": str(datetime.now()),
        "status": "INSERT",
    }
    shipping = {
        "shipping_id": shipping_id,
        "shipping_address": random.choices([user["address"], fake.address()], [0.9, 0.1])[0],
        "shipping_cost": round(random.uniform(0, 30), 2),
        "shipping_status": random.choices(SHIPPING_STATUSES)[0],
        "last_modified_ts": str(datetime.now()),
        "status": "INSERT",
    }
    return transaction, shipping


def seed_transactions_and_shippings(session, users, products, payments):
    transactions = []
    shippings = []
    for _ in range(TRANSACTION_LENGTH):
        transaction, shipping = generate_transaction_shipping(users, products, payments)
        transactions.append(transaction)
        shippings.append(shipping)

    bulk_insert(session, Shipping, shippings)
    bulk_insert(session, Transaction, transactions)
    return transactions, shippings


def pop_random(pool):
    idx = random.randrange(len(pool))
    pool[idx], pool[-1] = pool[-1], pool[idx]
    return pool.pop()


def peek_random(pool):
    return pool[random.randrange(len(pool))]


def run_continuous(session, pools, interval):
    """Keep mutating Postgres after the initial seed so Debezium keeps emitting
    a live mix of INSERT/UPDATE/DELETE CDC events instead of going idle. Runs
    until Ctrl+C. DELETEs are scoped to transactions/shippings only (order
    cancellation is a realistic delete; users/products/payments are treated
    as slower-changing reference data that only gets inserted/updated).
    """
    print(f"[continuous] running every {interval}s, Ctrl+C to stop")
    try:
        while True:
            op = random.choices(["insert", "update", "delete"], weights=[0.5, 0.4, 0.1])[0]

            if op == "insert":
                entity = random.choices(
                    ["transaction", "user", "product", "payment"],
                    weights=[0.55, 0.15, 0.15, 0.15],
                )[0]
                if entity == "transaction":
                    transaction, shipping = generate_transaction_shipping(
                        pools["user"], pools["product"], pools["payment"]
                    )
                    bulk_insert(session, Shipping, [shipping])
                    bulk_insert(session, Transaction, [transaction])
                    pools["shipping"].append(shipping)
                    pools["transaction"].append(transaction)
                elif entity == "user":
                    user = data_generator.generate_user()
                    user["last_modified_ts"] = str(datetime.now())
                    bulk_insert(session, User, [user])
                    pools["user"].append(user)
                elif entity == "product":
                    product = data_generator.generate_product()
                    product["last_modified_ts"] = str(datetime.now())
                    bulk_insert(session, Product, [product])
                    pools["product"].append(product)
                elif entity == "payment":
                    payment = {
                        "payment_id": str(uuid.uuid4()),
                        "payment_method": random.choice(PAYMENT_METHODS),
                        "currency": fake.currency_code(),
                        "status": "INSERT",
                        "last_modified_ts": str(datetime.now()),
                    }
                    bulk_insert(session, Payment, [payment])
                    pools["payment"].append(payment)

            elif op == "update":
                entity = random.choice(["user", "product", "payment", "shipping", "transaction"])
                pool = pools[entity]
                if not pool:
                    continue
                row = peek_random(pool)
                values = {"last_modified_ts": str(datetime.now()), "status": "UPDATE"}
                if entity == "product":
                    values["unit_price"] = round(random.uniform(10, 100), 2)
                elif entity == "shipping":
                    values["shipping_status"] = random.choice(SHIPPING_STATUSES)
                model, pk = MODEL_PK[entity]
                update_row(session, model, pk, row[pk], values)

            else:  # delete
                entity = random.choice(["shipping", "transaction"])
                pool = pools[entity]
                if not pool:
                    continue
                row = pop_random(pool)
                model, pk = MODEL_PK[entity]
                delete_row(session, model, pk, row[pk])

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[continuous] stopped")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic e-commerce data into Postgres")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="After the initial seed, keep generating random INSERT/UPDATE/DELETE events indefinitely",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds to sleep between events in --continuous mode (default: 5)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    session = create_session(host, port, username, password, db_name)

    users = seed_users(session)
    products = seed_products(session)
    payments = seed_payments(session)
    transactions, shippings = seed_transactions_and_shippings(session, users, products, payments)

    if args.continuous:
        pools = {
            "user": users,
            "product": products,
            "payment": payments,
            "shipping": shippings,
            "transaction": transactions,
        }
        run_continuous(session, pools, args.interval)

    session.close()


if __name__ == "__main__":
    main()
