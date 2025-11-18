"""
Main Application File - Handles app initialization, authentication and main routes
"""

from flask import Flask, request, redirect, render_template, url_for, session, jsonify
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env locally; harmless on Render
except Exception:
    pass
from db_connect import client
import os
import threading
import time
import requests
from datetime import datetime
from werkzeug.security import check_password_hash
from inventory import inventory_bp
from patient_form import patient_bp
from payments import payments_bp
from pharmacy import pharmacy_bp
from reports import reports_bp

USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Needed for sessions

# Keep-alive configuration``
KEEP_ALIVE_ENABLED = os.getenv("KEEP_ALIVE_ENABLED", "1") == "1"
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "840"))  # 14 minutes
APP_URL = os.getenv("APP_URL", "ims-2024.onrender.com")  # Set this to your Render app URL

# Register Blueprints
app.register_blueprint(inventory_bp, url_prefix='/inventory')
app.register_blueprint(patient_bp, url_prefix='/patient')
app.register_blueprint(payments_bp, url_prefix='/payments')
app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy')
app.register_blueprint(reports_bp, url_prefix='/reports')

# --- Authentication Routes ---

@app.route("/", methods=["GET", "POST"])
def login():
    """Handle user login"""
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        res = client.execute("SELECT password_hash FROM Users WHERE username = ?1", [username])
        if not res.rows:
            error = "Invalid username or password."
        else:
            stored_hash = res.rows[0][0]
            if check_password_hash(stored_hash, password):
                session["username"] = username
                return redirect(url_for("patient.patient_form"))
            else:
                error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    """Handle user logout"""
    session.pop("username", None)
    return redirect(url_for("login"))

# --- Keep-Alive Routes ---

@app.route("/health")
def health_check():
    """Health check endpoint for keep-alive pings"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "IMS System is running"
    })

@app.route("/keep-alive")
def keep_alive():
    """Simple keep-alive endpoint"""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    })

# --- Main Navigation Routes ---

@app.route("/pharmacy")
def pharmacy():
    """Redirect to pharmacy blueprint so data loads correctly in the blueprint route"""
    if "username" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("pharmacy.pharmacy")) # Because the data is loaded in the blueprint route

@app.route("/view-sales", methods=["GET", "POST"])
def view_sales():
    if "username" not in session:
        return redirect(url_for("login"))

    from db_connect import client

    # --- Default: today's date ---
    today = datetime.now().strftime("%Y-%m-%d")
    selected_date = request.form.get("date", today)
    uhid = request.form.get("uhid", "").strip()
    invoice_id = request.form.get("invoiceid", "").strip()  # ← user input
    phone = request.form.get("phonenum", "").strip()
    pname = request.form.get("pname", "").strip()

    # --- Base Query using your view ---
    query = "SELECT * FROM vw_dailyPharmacyDetailsDemo WHERE 1=1"
    params = []

    # --- Filters ---
    if selected_date:
        query += " AND substr(timestamp, 1, 10) = ?"
        params.append(selected_date)

    if pname:
        query += " AND PName LIKE ?"
        params.append(f"%{pname}%")

    if uhid:
        query += " AND UHId LIKE ?"
        params.append(f"%{uhid}%")

    if invoice_id:
        query += " AND InvoiceId LIKE ?"
        params.append(f"%{invoice_id}%")

    if phone:
        query += " AND PhoneNo LIKE ?"
        params.append(f"%{phone}%")

    query += " ORDER BY timestamp DESC, InvoiceId"

    # --- Fetch filtered sales data ---
    try:
        result = client.execute(query, params)
        sales_data = result.rows
    except Exception as e:
        print("❌ Error fetching sales data:", e)
        sales_data = []

    # --- Group data by InvoiceId ---
    grouped_invoices = {}
    total_btotal = 0

    for row in sales_data:
        row_invoice_id = row[11]  # ← FIXED: use a different variable

        if row_invoice_id not in grouped_invoices:
            grouped_invoices[row_invoice_id] = []

        grouped_invoices[row_invoice_id].append(row)

        # BTotal is index 8
        if row[8] and row[8] != "":
            try:
                total_btotal += float(row[8])
            except (ValueError, TypeError):
                pass

    # --- Summary ---
    summary_query = """
        SELECT 
            COUNT(DISTINCT InvoiceId) AS total_invoices,
            SUM(CASE WHEN PaymentMode = 'Cash' THEN TotalAmount ELSE 0 END) AS cash_total,
            SUM(CASE WHEN PaymentMode = 'UPI' THEN TotalAmount ELSE 0 END) AS upi_total
        FROM MedicineInvoices
        WHERE DATE(InvoiceDate) = ?
    """

    summary_result = (
        client.execute(summary_query, [selected_date]).rows[0]
        if client else (0, 0, 0)
    )

    summary = {
        "total_invoices": summary_result[0] if summary_result else 0,
        "cash_total": summary_result[1] if summary_result else 0,
        "upi_total": summary_result[2] if summary_result else 0,
        "total_btotal": round(total_btotal, 2)
    }

    # --- Label text ---
    label = f"Showing data for {datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d-%b-%y')}"

    if pname:
        label = f"Showing data for patient name - {pname}"
    elif uhid:
        label = f"Showing data for UHID - {uhid}"
    elif invoice_id:
        label = f"Showing data for Invoice ID - {invoice_id}"
    elif phone:
        label = f"Showing data for Phone - {phone}"

    return render_template(
        "view_sales.html",
        active_page="view_sales",
        sales_data=sales_data,
        grouped_invoices=grouped_invoices,
        label=label,
        summary=summary,
        selected_date=selected_date,
        pname=pname,
        uhid=uhid,
        invoice_id=invoice_id,  # ← stays user input only
        phone=phone
    )

@app.route("/returns")
def returns():
    """Returns management page"""
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("returns.html", active_page="returns")

@app.route("/price-update")
def price_update():
    """Price update page"""
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("price_update.html", active_page="price_update")

# --- Keep-Alive Background Service ---

def keep_alive_service():
    """Background service to ping the app and prevent sleeping"""
    if not KEEP_ALIVE_ENABLED or not APP_URL:
        return
    
    def ping_app():
        while True:
            try:
                time.sleep(KEEP_ALIVE_INTERVAL)  # Wait before first ping
                response = requests.get(f"{APP_URL}/health", timeout=30)
                if response.status_code == 200:
                    print(f"[{datetime.now().isoformat()}] Keep-alive ping successful")
                else:
                    print(f"[{datetime.now().isoformat()}] Keep-alive ping failed: {response.status_code}")
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] Keep-alive ping error: {str(e)}")
    
    # Start the ping thread
    ping_thread = threading.Thread(target=ping_app, daemon=True)
    ping_thread.start()
    print(f"[{datetime.now().isoformat()}] Keep-alive service started (interval: {KEEP_ALIVE_INTERVAL}s)")

# --- Application Entry Point ---

if __name__ == "__main__" and USE_SQLITE == 1:
    if KEEP_ALIVE_ENABLED:
        keep_alive_service()
    app.run(debug=True, use_reloader=False)
elif __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    if KEEP_ALIVE_ENABLED:
        keep_alive_service()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)