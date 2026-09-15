-- Hot + cold serving views (PLAN.md 4.3). Pinot holds the freshest version of
-- every recently changed row; Iceberg holds everything as of the last merge.
-- Each view returns all Pinot rows, plus Iceberg rows whose key Pinot doesn't
-- have. No date split: Pinot's `date` comes from the generator's local clock
-- while staging partitions use Spark's UTC clock, and a key-based split is
-- correct regardless. Column lists follow the Pinot schemas (e.g. Pinot has
-- no shipping_status).

CREATE SCHEMA IF NOT EXISTS iceberg.serving;

CREATE OR REPLACE VIEW iceberg.serving.users AS
SELECT user_id, full_name, phone_number, sex, address, email, job, status, birthdate, last_modified_ts, 'pinot' AS served_from
FROM pinot.default.users
UNION ALL
SELECT c.user_id, c.full_name, c.phone_number, c.sex, c.address, c.email, c.job, c.status, c.birthdate, c.last_modified_ts, 'iceberg'
FROM iceberg.cdc.users c
WHERE NOT EXISTS (SELECT 1 FROM pinot.default.users h WHERE h.user_id = c.user_id);

CREATE OR REPLACE VIEW iceberg.serving.products AS
SELECT product_id, product_name, category, merchant_name, status, unit_price, rating, last_modified_ts, 'pinot' AS served_from
FROM pinot.default.products
UNION ALL
SELECT c.product_id, c.product_name, c.category, c.merchant_name, c.status, c.unit_price, c.rating, c.last_modified_ts, 'iceberg'
FROM iceberg.cdc.products c
WHERE NOT EXISTS (SELECT 1 FROM pinot.default.products h WHERE h.product_id = c.product_id);

CREATE OR REPLACE VIEW iceberg.serving.payments AS
SELECT payment_id, payment_method, currency, status, last_modified_ts, 'pinot' AS served_from
FROM pinot.default.payments
UNION ALL
SELECT c.payment_id, c.payment_method, c.currency, c.status, c.last_modified_ts, 'iceberg'
FROM iceberg.cdc.payments c
WHERE NOT EXISTS (SELECT 1 FROM pinot.default.payments h WHERE h.payment_id = c.payment_id);

CREATE OR REPLACE VIEW iceberg.serving.shippings AS
SELECT shipping_id, shipping_address, status, shipping_cost, last_modified_ts, 'pinot' AS served_from
FROM pinot.default.shippings
UNION ALL
SELECT c.shipping_id, c.shipping_address, c.status, c.shipping_cost, c.last_modified_ts, 'iceberg'
FROM iceberg.cdc.shippings c
WHERE NOT EXISTS (SELECT 1 FROM pinot.default.shippings h WHERE h.shipping_id = c.shipping_id);

CREATE OR REPLACE VIEW iceberg.serving.transactions AS
SELECT transaction_id, user_id, product_id, payment_id, shipping_id, status, quantity, discount, last_modified_ts, 'pinot' AS served_from
FROM pinot.default.transactions
UNION ALL
SELECT c.transaction_id, c.user_id, c.product_id, c.payment_id, c.shipping_id, c.status, c.quantity, c.discount, c.last_modified_ts, 'iceberg'
FROM iceberg.cdc.transactions c
WHERE NOT EXISTS (SELECT 1 FROM pinot.default.transactions h WHERE h.transaction_id = c.transaction_id);
