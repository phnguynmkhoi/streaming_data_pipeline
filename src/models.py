from sqlalchemy import Column, VARCHAR, Float, UUID, CHAR, INTEGER
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(), primary_key=True)
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

    product_id = Column(UUID(), primary_key=True)
    product_name = Column(VARCHAR(100))
    category = Column(VARCHAR(100))
    unit_price = Column(Float)
    merchant_name = Column(VARCHAR(100))
    rating = Column(Float)
    last_modified_ts = Column(VARCHAR(100))
    status = Column(VARCHAR(50))


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(UUID(), primary_key=True)
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
