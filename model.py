from sqlalchemy import create_engine, Column, Integer, String, UUID, Float, Time
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
class Transaction(Base):
    __tablename__ = "transactions"    

    transaction_id = Column(UUID(), primary_key=True, nullable=False)
    user_id = Column(UUID(),nullable=False)
    timestamp = Column(Time())
    amount = Column(Float())
    currency = Column(String(200))
    city = Column(String(200))
    country = Column(String(200))
    merchant_name = Column(String(200))
    payment_method = Column(String(200))
    ip_address = Column(String(200))
    voucher_code = Column(String(200))
    affiliate_id = Column(UUID(),nullable=False)

    
