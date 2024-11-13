import faker
import random
from datetime import datetime
import uuid

import faker_commerce

fake = faker.Faker()
fake.add_provider(faker_commerce.Provider)

class DataGenerator:
    def __init__(self):
        pass
    def generate_user(self):
        user = fake.profile()
        new_user = {
            "user_id": str(uuid.uuid4()),
            "full_name": user["name"],
            "sex": user["sex"],
            "phone_number": fake.phone_number(),
            "birthdate": user["birthdate"],
            "email": user["mail"],
            "job": user["job"],
            "address": user["address"],
            "status": "INSERT"
        }
        return new_user

    def generate_product(self):
        product = {}
        product["product_id"] = str(uuid.uuid4())
        product["product_name"] = fake.ecommerce_name()
        product["category"] = fake.ecommerce_category()
        product["unit_price"] = round(random.uniform(10,100),2)
        product["merchant_name"] = fake.company()
        product["rating"] = random.random()*5
        product["status"] = "INSERT"

        return product

    # def generate_payment(self):
    #     self.payment = {}
    #     self.payment["payment_id"] = uuid.uuid4()
    #     self.payment["payment_method"] = random.choice(['Visa', 'Mastercard', 'Credit Card', 'Debit Card','Paypal'])
    #     self.payment["currency"] = fake.currency_code()
    
    def generate(self):
        user = self.generate_user()
        product = self.generate_product()
        return user, product
    

# def generate_transaction():
#     user = fake.profile()
#     transaction = {}
#     transaction["transaction_id"] = str(uuid.uuid4())
#     transaction["quantity"] = random.randint(1,10)
#     transaction["discount"] = random.choices([15,10,5,0],[0.05,0.05,0.1,0.8])[0]
#     transaction["shipping_address"] = random.choices([user["address"],fake.address()],[0.9,0.1])[0]
#     transaction["shipping_cost"] = round(random.uniform(0,30),2)
#     transaction["created_at"] = datetime.now().strftime("%y/%M/%d %H:%M:%S")
    
#     return transaction

# if __name__=="__main__":
#     print(generate_user())
    