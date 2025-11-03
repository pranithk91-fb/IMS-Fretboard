from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime
from db_connect import client
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pharmacy_bp = Blueprint('pharmacy', __name__)

@pharmacy_bp.route('/api/medicine-details/<medicine_name>', methods=['GET'])
def get_medicine_details(medicine_name):
    """API endpoint to fetch medicine details by name - MRP, MType from MedicineList, BatchNo from StockDeliveries"""
    try:
        logger.info(f"🔍 [API] Fetching details for medicine: '{medicine_name}'")
        
        # Get MRP and MType from MedicineList
        medicine_data = {
            'MRP': None,
            'MType': None,
            'BatchNo': None
        }
        
        try:
            # Query MedicineList for MRP and MType
            medicine_query = """
                SELECT MRP, MType
                FROM MedicineList 
                WHERE TRIM(MName) = TRIM(?) COLLATE NOCASE
                LIMIT 1
            """
            logger.info(f"📊 [API] Querying MedicineList with MName = '{medicine_name}'")
            medicine_result = client.execute(medicine_query, [medicine_name])
            
            if hasattr(medicine_result, 'rows') and medicine_result.rows:
                logger.info(f"✓ [API] Found {len(medicine_result.rows)} row(s) in MedicineList")
                row = medicine_result.rows[0]
                medicine_data['MRP'] = row[0]
                medicine_data['MType'] = row[1]
                logger.info(f"✓ [API] MRP: {medicine_data['MRP']}, MType: {medicine_data['MType']}")
            else:
                logger.warning(f"⚠ [API] No matching medicine found in MedicineList for '{medicine_name}'")
                return jsonify({
                    'success': False,
                    'message': f'Medicine "{medicine_name}" not found in database'
                }), 404
                
        except Exception as med_error:
            logger.error(f"❌ [API] Error querying MedicineList: {str(med_error)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Database error: {str(med_error)}'
            }), 500
        
        # Get latest BatchNo from StockDeliveries (fallback to OldDeliveries)
        try:
            batch_query = """
                SELECT BatchNo
                FROM StockDeliveries 
                WHERE TRIM(MName) = TRIM(?) COLLATE NOCASE
                ORDER BY DeliveryDate DESC
                LIMIT 1
            """
            logger.info(f"📦 [API] Querying StockDeliveries for BatchNo with MName = '{medicine_name}'")
            batch_result = client.execute(batch_query, [medicine_name])
            
            if hasattr(batch_result, 'rows') and batch_result.rows and len(batch_result.rows) > 0:
                batch_no = batch_result.rows[0][0]
                if batch_no:  # Only set if not NULL
                    medicine_data['BatchNo'] = batch_no
                    logger.info(f"✓ [API] Found BatchNo in StockDeliveries: {medicine_data['BatchNo']}")
                else:
                    logger.info(f"⚠ [API] BatchNo is NULL in StockDeliveries")
            else:
                logger.info(f"⚠ [API] No batch records found in StockDeliveries for '{medicine_name}', checking OldDeliveries…")
                # Fallback: OldDeliveries may not have DeliveryDate; use rowid DESC as latest heuristic
                old_deliveries_query = """
                    SELECT BatchNo
                    FROM OldDeliveries
                    WHERE TRIM(MName) = TRIM(?) COLLATE NOCASE
                      AND BatchNo IS NOT NULL AND TRIM(BatchNo) <> ''
                    ORDER BY rowid DESC
                    LIMIT 1
                """
                old_result = client.execute(old_deliveries_query, [medicine_name])
                if hasattr(old_result, 'rows') and old_result.rows and len(old_result.rows) > 0:
                    old_batch = old_result.rows[0][0]
                    medicine_data['BatchNo'] = old_batch
                    logger.info(f"✓ [API] Found BatchNo in OldDeliveries: {old_batch}")
                else:
                    logger.info(f"⚠ [API] No BatchNo found in OldDeliveries either")
                
        except Exception as batch_error:
            logger.warning(f"⚠ [API] Error querying StockDeliveries (non-critical): {str(batch_error)}")
            
        
        # Step 3: Return the data
        logger.info(f"✅ [API] Final payload: MRP={medicine_data['MRP']}, MType={medicine_data['MType']}, BatchNo={medicine_data['BatchNo']}")
        return jsonify({
            'success': True,
            'data': medicine_data
        })
            
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Unexpected error: {str(e)}'
        }), 500

# Alternate endpoint that accepts query param (more robust routing)
@pharmacy_bp.route('/api/medicine-details', methods=['GET'])
def api_medicine_details_query():
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'name is required'}), 400
    return get_medicine_details(name)

def generate_uhid():
    """Generate a new UHId based on date and existing records"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        year_month = datetime.now().strftime('%y%m')  # YYMM format
        
        # Get today's patients to find the next available letter+number combo
        result = client.execute("""
            SELECT UHId FROM Patients 
            WHERE substr(Date, 1, 10) = ?
            ORDER BY UHId DESC
            LIMIT 1
        """, [today])
        
        if hasattr(result, 'rows') and result.rows:
            last_uhid = result.rows[0][0]
            # Extract the numeric part (last 3 digits)
            if last_uhid and len(last_uhid) >= 7:
                try:
                    last_num = int(last_uhid[-3:])
                    next_num = last_num + 1
                    # Use letters in rotation: A, B, C, ... Z
                    letter = chr(65 + (next_num // 100) % 26)  # A=65
                    return f"{year_month}{letter}{next_num:03d}"
                except:
                    pass
        
        # Default: start with A001
        return f"{year_month}A001"
    except Exception as e:
        logger.error(f"Error generating UHId: {str(e)}")
        return f"{datetime.now().strftime('%y%m')}A001"

@pharmacy_bp.route('/', methods=['GET', 'POST'])
def pharmacy():
    try:
        if request.method == 'POST':
            # Process prescription submission
            patient_name = request.form.get('patient_name', '').strip()
            phone_no = request.form.get('phone_no', '').strip()
            uhid = request.form.get('uhid', '').strip()
            age = request.form.get('age', '').strip()
            gender = request.form.get('gender', '').strip()
            payment_mode = (request.form.get('payment_mode', '') or '').strip()
            cash_amount_raw = (request.form.get('cash_amount', '') or '').strip()
            upi_amount_raw = (request.form.get('upi_amount', '') or '').strip()
            
            # Validate required fields
            if not patient_name:
                flash('Patient name is required', 'error')
                return redirect(url_for('pharmacy.pharmacy'))
            
            # Check if this is a new patient (no UHId or not in today's patients)
            if not uhid:
                logger.info(f"🆕 New patient detected: {patient_name}")

                # Only add to Patients table if phone number is provided; otherwise continue without registering
                if phone_no:
                    try:
                        # Generate new UHId
                        uhid = generate_uhid()
                        today_date = datetime.now().strftime('%Y-%m-%d')

                        # Insert new patient record
                        client.execute("""
                            INSERT INTO Patients (UHId, Date, PName, PhoneNo, Age, Gender)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, [uhid, today_date, patient_name, phone_no, age if age else None, gender if gender else None])

                        logger.info(f"✓ New patient added to database: {patient_name} (UHId: {uhid})")
                        flash(f'New patient registered with UHId: {uhid}', 'info')
                    except Exception as patient_error:
                        logger.error(f"❌ Error adding new patient: {str(patient_error)}")
                        flash('Could not register patient in database', 'warning')
                        uhid = f"TEMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    # No phone provided; do not add to Patients table and proceed without UHId (use TEMP for linkage)
                    logger.info(f"ℹ New patient '{patient_name}' without phone number - skipping Patients table insert")
                    uhid = f"TEMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Get medicines data
            medicines = []
            i = 1
            while f'medicine_{i}' in request.form:
                medicine = {
                    'name': request.form.get(f'medicine_{i}'),
                    'quantity': int(request.form.get(f'quantity_{i}')),
                    'price': float(request.form.get(f'price_{i}')),
                    'dosage': request.form.get(f'dosage_{i}'),
                    'duration': request.form.get(f'duration_{i}'),
                    'total': float(request.form.get(f'total_{i}'))
                }
                medicines.append(medicine)
                i += 1
            
            if not medicines:
                flash('Please add at least one medicine', 'error')
                return redirect(url_for('pharmacy.pharmacy'))
            
            # Calculate total amount
            total_amount = sum(med['total'] for med in medicines)

            # Normalize payment inputs
            def _to_float(value: str) -> float:
                try:
                    return float(value)
                except Exception:
                    return 0.0

            cash_amount = _to_float(cash_amount_raw)
            upi_amount = _to_float(upi_amount_raw)

            if payment_mode == 'Cash':
                cash_amount = total_amount
                upi_amount = 0.0
            elif payment_mode == 'UPI':
                upi_amount = total_amount
                cash_amount = 0.0
            elif payment_mode == 'Both':
                # If client sent mismatched values, cap to total and adjust
                if cash_amount < 0:
                    cash_amount = 0.0
                if upi_amount < 0:
                    upi_amount = 0.0
                s = cash_amount + upi_amount
                if abs(s - total_amount) > 0.01:
                    logger.warning(f"[Pharmacy] Payment split mismatch: cash={cash_amount}, upi={upi_amount}, total={total_amount}. Adjusting upi part.")
                    upi_amount = max(0.0, total_amount - cash_amount)
            else:
                # Default fallback to Cash if not provided
                payment_mode = 'Cash'
                cash_amount = total_amount
                upi_amount = 0.0
            
            # Insert prescription record
            prescription_id = f"RX-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            client.execute("""
                INSERT INTO Prescriptions (
                    PrescriptionId, PatientName, PhoneNo, UHId, 
                    TotalAmount, CreatedDate
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                prescription_id, patient_name, phone_no, uhid,
                total_amount, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])

            # Insert medicine details
            for medicine in medicines:
                client.execute("""
                    INSERT INTO PrescriptionMedicines (
                        PrescriptionId, MedicineName, Quantity, Price,
                        Dosage, Duration, Total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    prescription_id, medicine['name'], medicine['quantity'],
                    medicine['price'], medicine['dosage'], medicine['duration'],
                    medicine['total']
                ])
            
            flash(f'Prescription {prescription_id} created successfully! Payment: {payment_mode} (Cash ₹{cash_amount:.2f}, UPI ₹{upi_amount:.2f})', 'success')
            return redirect(url_for('pharmacy.pharmacy'))
        
        # GET request - display form
        # Get today's registered patients strictly by Date
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            # Debug: Check what Date values actually exist in the database
            debug_result = client.execute("""
                SELECT DISTINCT substr(TRIM(Date), 1, 10) as DateShort, Date as DateFull, COUNT(*) as cnt
                FROM Patients 
                GROUP BY DateShort
                ORDER BY DateShort DESC
                LIMIT 5
            """)
            logger.info(f"[Pharmacy] DEBUG: Sample Date values in database:")
            if hasattr(debug_result, 'rows') and debug_result.rows:
                for row in debug_result.rows[:5]:
                    logger.info(f"  DateShort: '{row[0]}', DateFull: '{row[1]}', Count: {row[2]}")
            else:
                logger.warning("[Pharmacy] DEBUG: No rows returned from debug query")
            
            logger.info(f"[Pharmacy] DEBUG: Looking for patients with Date matching: '{today}'")
            
            # TEST: Try fetching 2025-10-23 (which we know exists) to verify query works
            test_date = "2025-10-23"
            test_result = client.execute("""
                SELECT DISTINCT PName, PhoneNo, UHId 
                FROM Patients 
                WHERE Date = ?
                ORDER BY PName
            """, [test_date])
            test_count = len(getattr(test_result, 'rows', []) or [])
            logger.info(f"[Pharmacy] TEST: Query for {test_date} returned {test_count} patient(s)")
            if test_count > 0:
                logger.info(f"[Pharmacy] TEST: Sample rows from {test_date}: {test_result.rows[:2]}")
            
            # Try multiple query formats for today
            patients_result = client.execute("""
                SELECT DISTINCT PName, PhoneNo, UHId 
                FROM Patients 
                WHERE Date = ?
                ORDER BY PName
            """, [today])
            
            row_count = len(getattr(patients_result, 'rows', []) or [])
            logger.info(f"[Pharmacy] Loaded {row_count} patient(s) for date {today}")
            
            # If no results, try alternative queries
            if row_count == 0:
                logger.info(f"[Pharmacy] Trying alternative query with substr: substr(TRIM(Date), 1, 10) = '{today}'")
                patients_result = client.execute("""
                    SELECT DISTINCT PName, PhoneNo, UHId 
                    FROM Patients 
                    WHERE substr(TRIM(Date), 1, 10) = ?
                    ORDER BY PName
                """, [today])
                row_count = len(getattr(patients_result, 'rows', []) or [])
                logger.info(f"[Pharmacy] Alternative query returned {row_count} patient(s)")
                
                # Also check if there's a patient with UHId 2510A0143 (from the image)
                specific_uhid = "2510A0143"
                specific_result = client.execute("""
                    SELECT PName, PhoneNo, UHId, Date
                    FROM Patients 
                    WHERE UHId = ?
                """, [specific_uhid])
                if hasattr(specific_result, 'rows') and specific_result.rows:
                    logger.info(f"[Pharmacy] Found patient with UHId {specific_uhid}: Date='{specific_result.rows[0][3]}'")

            if row_count > 0:
                logger.info(f"[Pharmacy] Sample patient rows: {patients_result.rows[:3]}")
            today_patients = [dict(zip(['PName', 'Phone', 'UHId'], row)) for row in getattr(patients_result, 'rows', [])]
        except Exception as patient_load_err:
            logger.error(f"✗ Error loading today's patients: {str(patient_load_err)}", exc_info=True)
            today_patients = []
        
        # Get available medicines from MedicineList table
        medicines = []
        try:
            logger.info("🔍 Attempting to load medicines from MedicineList table...")
            medicines_result = client.execute("""
                SELECT MId, MName, MRP, MCompany, CurrentStock, MType
                FROM MedicineList 
                WHERE MRP IS NOT NULL
                ORDER BY MName
            """)
            
            # Debug: Log the raw result
            logger.info(f"Query executed. Result type: {type(medicines_result)}")
            logger.info(f"Result has rows: {hasattr(medicines_result, 'rows')}")
            
            if hasattr(medicines_result, 'rows'):
                logger.info(f"Number of rows: {len(medicines_result.rows)}")
                medicines = [dict(zip(['MId', 'MName', 'MRP', 'MCompany', 'CurrentStock', 'MType'], row)) for row in medicines_result.rows]
                logger.info(f"✓ Successfully loaded {len(medicines)} medicines from database")
                
                # Debug: Print first 3 medicines
                if medicines:
                    logger.info(f"Sample medicines: {medicines[:3]}")
            else:
                logger.error("❌ Result doesn't have 'rows' attribute")
                medicines = []
            
            # If no medicines found, log a warning
            if not medicines:
                logger.warning("⚠ No medicines found in MedicineList table")
                flash('No medicines available in the database', 'warning')
        except Exception as med_error:
            logger.error(f"✗ Error loading medicines: {str(med_error)}", exc_info=True)
            medicines = []
            flash(f'Error loading medicines: {str(med_error)}', 'error')
        
        return render_template('pharmacy.html', 
                             today_patients=today_patients,
                             medicines=medicines,
                             today_date=today,
                             active_page='pharmacy')
        
    except Exception as e:
        logger.error(f"❌ Error in pharmacy route: {str(e)}", exc_info=True)
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('pharmacy.html', 
                             today_patients=[],
                             medicines=[],
                             today_date=datetime.now().strftime('%Y-%m-%d'),
                             active_page='pharmacy')