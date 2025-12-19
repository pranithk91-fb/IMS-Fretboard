from db_connect import client

query = """
SELECT InvoiceId, PName, MName, Mstock AS Quantity, MTotal, TotalAmc AS BTotal,
       Discount, paymentM AS PaymentMode, Comments
FROM vw_dailyPharmacyDetails
ORDER BY InvoiceId DESC
LIMIT 20
"""

result = client.execute(query)    # returns a ResultSet object with .rows (libsql)
rows = result.rows                # list of tuples

# map to dicts (use your column names)
cols = ["InvoiceId","PName","MName","Quantity","MTotal","BTotal","Discount","PaymentMode","Comments"]
data = [dict(zip(cols, r)) for r in rows]

for d in data:
    print(d)
