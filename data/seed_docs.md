# Seed documents — Harbor & Pine Supply Co.

Short notes the shop keeps about how it talks about the business.
The ontology layer v0 was built from these plus the database schema.
They are loose on purpose: this is how a real first-pass semantic
layer gets built — from docs that say roughly the right thing.

## Doc 1 — How we talk about money

Revenue is total sales. An order's total is stored in cents in the
orders table. Payments have a status: paid, refunded, or failed.
Most orders are paid. The website takes orders online, the shop
floor takes them in-store, and a few come in by phone.

## Doc 2 — Customers and products

A VIP customer is one of our best customers — they get early access
to new stock. A product is discontinued when we stop selling it.
An active customer is someone who shops with us regularly. We
usually look at who signed up recently to find active customers.

## Doc 3 — What sells

The best-selling product is the one that shows up in the most
orders. Average order value is the average of the order totals.
The top customer is the one who has spent the most with us overall.
