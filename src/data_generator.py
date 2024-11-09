import faker
import random
from datetime import datetime

import faker_commerce

fake = faker.Faker()
fake.add_provider(faker_commerce.Provider)

def generate_transaction():
    user = fake.profile()
    transaction = {}
    transaction["transaction_id"] = fake.uuid4(),
    transaction["name"] = user["name"]
    transaction["sex"] = user["sex"]
    transaction["address"] = user["address"]
    transaction["phone_number"] = fake.phone_number()
    transaction["birthdate"] = user["birthdate"]
    transaction["email"] = user["mail"]
    transaction["job"] = user["job"]
    transaction["product_name"] = fake.ecommerce_name()
    transaction["category"] = fake.ecommerce_category()
    transaction["unit_price"] = round(random.uniform(10,100),2)
    transaction["quantity"] = random.randint(1,10)
    transaction["merchant_name"] = fake.company()
    transaction["payment_method"] = random.choice(['Visa', 'Mastercard', 'Credit Card', 'Debit Card','Paypal'])
    transaction["discount"] = random.choices([15,10,5,0],[0.05,0.05,0.1,0.8])[0]
    transaction["shipping_address"] = random.choices([user["address"],fake.address()],[0.9,0.1])[0]
    transaction["shipping_cost"] = round(random.uniform(0,30),2)
    transaction["total"] = transaction["unit_price"]*transaction["quantity"]*(1-transaction["discount"]) + transaction["shipping_cost"]
    transaction["currency"] = fake.currency_code()
    transaction["created_at"] = datetime.now()
    
    return transaction

if __name__=="__main__":
    print(generate_transaction())