from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime
from db_connect import client
import logging

pharmacy_bp = Blueprint('pharmacy', __name__)

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
        patients_result = client.execute("""
            SELECT DISTINCT PName, Phone, UHId 
            FROM Patients 
            WHERE DATE(RegisterDate) = ?
            ORDER BY PName
        """, [today])
        today_patients = [dict(zip(['PName', 'Phone', 'UHId'], row)) for row in patients_result]
        
        # Get available medicines
        medicines_result = client.execute("""
            SELECT MId, MedicineName, MRP 
            FROM mMedicines 
            WHERE MRP > 0
            ORDER BY MedicineName
        """)
        medicines = [dict(zip(['MId', 'MedicineName', 'MRP'], row)) for row in medicines_result]
        
        return render_template('pharmacy.html', 
                             today_patients=today_patients,
                             medicines=medicines,
                             today_date=today,
                             active_page='pharmacy')
        
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('pharmacy.html', 
                             today_patients=[],
                             medicines=[],
                             today_date=datetime.now().strftime('%Y-%m-%d'),
                             active_page='pharmacy')