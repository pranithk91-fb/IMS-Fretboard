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

@pharmacy_bp.route('/', methods=['GET', 'POST'])
def pharmacy():
    try:
        if request.method == 'POST':
            # Process prescription submission
            patient_name = request.form.get('patient_name')
            phone_no = request.form.get('phone_no') 
            uhid = request.form.get('uhid')
            
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
            
            flash(f'Prescription {prescription_id} created successfully!', 'success')
            return redirect(url_for('pharmacy.pharmacy'))
        
        # GET request - display form
        # Get today's registered patients
        today = datetime.now().strftime('%Y-%m-%d')
        # Use correct Patients schema: columns are PName, PhoneNo, UHId, Date
        # Match records for today using the first 10 chars of Date (YYYY-MM-DD)
        patients_result = client.execute("""
            SELECT DISTINCT PName, PhoneNo, UHId 
            FROM Patients 
            WHERE substr(Date, 1, 10) = ?
            ORDER BY PName
        """, [today])
        today_patients = [dict(zip(['PName', 'Phone', 'UHId'], row)) for row in patients_result.rows]
        
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