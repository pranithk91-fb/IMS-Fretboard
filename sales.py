from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from db_connect import client

sales_bp = Blueprint('sales', __name__)

def parse_date_input(date_input):
    """Convert DD-MM-YYYY → YYYY-MM-DD; fallback to today"""
    if not date_input:
        return datetime.now().strftime("%Y-%m-%d")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_input, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")

@sales_bp.route("/sales", methods=["GET"])
def view_sales():
    """Main View Sales Page"""
    date_input = request.args.get("date", "").strip()
    uhid = request.args.get("uhid", "").strip()
    invoice_id = request.args.get("invoice_id", "").strip()
    phone = request.args.get("phone", "").strip()

    selected_date = parse_date_input(date_input)

    # Build WHERE clause dynamically
    filters = ["substr(InvoiceId,1,10) = ?"]
    params = [selected_date]
    if uhid:
        filters.append("UHId = ?"); params.append(uhid)
    if invoice_id:
        filters.append("InvoiceId = ?"); params.append(invoice_id)
    if phone:
        filters.append("PhoneNo = ?"); params.append(phone)

    where_clause = " AND ".join(filters)

    # Fetch sales data
    query = f"""
        SELECT 
            substr(InvoiceId,1,16) AS Timestamp,
            PName,
            MName,
            Mstock AS Quantity,
            MTotal,
            TotalAmc AS BTotal,
            Discount,
            paymentM AS PaymentMode,
            Comments,
            InvoiceId
        FROM vw_dailyPharmacyDetails
        WHERE {where_clause}
        ORDER BY InvoiceId DESC
    """
    result = client.execute(query)
    rows = result.rows
    columns = ["Timestamp","PName","MName","Quantity","MTotal","BTotal","Discount","PaymentMode","Comments","InvoiceId"]
    sales_data = [dict(zip(columns, r)) for r in rows]

    # Daily summary
    summary_query = f"""
        SELECT 
            COUNT(DISTINCT InvoiceId),
            SUM(CASE WHEN paymentM LIKE '%Cash%' THEN TotalAmc ELSE 0 END),
            SUM(CASE WHEN paymentM LIKE '%UPI%' THEN TotalAmc ELSE 0 END)
        FROM vw_dailyPharmacyDetails
        WHERE {where_clause}
    """
    sres = client.execute(summary_query, params)
    invoice_count, cash_total, upi_total = sres.rows[0] if sres.rows else (0, 0, 0)

    # Label for top info bar
    if not any([uhid, invoice_id, phone]):
        label = f"Showing data for {datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d-%b-%Y')}"
    elif uhid:
        label = f"Showing data for UHId - {uhid}"
    elif invoice_id:
        label = f"Showing data for Invoice - {invoice_id}"
    elif phone:
        label = f"Showing data for Phone - {phone}"

    return render_template(
        "view_sales.html",
        sales_data=sales_data,
        summary={
            "invoice_count": invoice_count,
            "cash_total": cash_total or 0,
            "upi_total": upi_total or 0,
        },
        label=label,
        selected_date=datetime.strptime(selected_date, "%Y-%m-%d").strftime("%d-%m-%Y"),
        uhid=uhid,
        invoice_id=invoice_id,
        phone=phone,
        active_page="view_sales"
    )

# Optional JSON debug endpoint
@sales_bp.route("/sales/debug", methods=["GET"])
def debug_sales_data():
    result = client.execute("SELECT * FROM vw_dailyPharmacyDetails LIMIT 10")
    return jsonify({"rows": result.rows})
