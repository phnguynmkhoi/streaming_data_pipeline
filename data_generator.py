import faker

fake = faker.Faker()

def generate_transaction():
    user = fake.simple_profile()

    return {
        "transaction_id": fake.uuid4(),
        "user_id": user['username'],
        "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
        "amount": round(random.uniform(10, 1000), 2),
        "currency": random.choice(['USD', 'EUR', 'GBP']),
        "city": fake.city(),
        "country": fake.country(),
        "merchant_name": fake.company(),
        "payment_method": random.choice(['Visa', 'Mastercard', 'Credit Card', 'Debit Card','Paypal']),
        "ip_address": fake.ipv4(),
        "voucher_code": random.choice(["","DISCOUNT10","",""]),
        'affiliate_id': fake.uuid4()
    }