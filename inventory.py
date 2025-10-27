from flask import Blueprint, render_template, request, session, abort, jsonify, redirect, url_for, flash
from db_connect import client
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/', methods=['GET', 'POST'])
def inventory():
    if request.method == 'GET':
        try:
            # Get agency list
            agency_query = "SELECT DISTINCT AgencyName FROM mAgencies WHERE AgencyName IS NOT NULL ORDER BY AgencyName"
            agency_result = client.execute(agency_query)
            agency_list = [row[0] for row in agency_result.rows if row[0]]
            
            # Get medicine list
            med_query = "SELECT DISTINCT MName FROM MedicineList WHERE MName IS NOT NULL ORDER BY MName"
            med_result = client.execute(med_query)
            med_list = [row[0] for row in med_result.rows if row[0]]
            
            return render_template('inventory.html', 
                                 agency_list=agency_list, 
                                 med_list=med_list)
                                 
        except Exception as e:
            logging.error(f"Error loading inventory page: {e}")
            flash('Error loading page data', 'error')
            return render_template('inventory.html', 
                                 agency_list=[], 
                                 med_list=[])
    
    elif request.method == 'POST':
        logging.info("Starting bill and inventory save process")
        try:
            # Extract bill data
            logging.info("Extracting bill data from form")
            bill_data = {
                'BillDate': request.form.get('BillDate'),
                'BillNo': request.form.get('BillNo'),
                'DeliveryDate': request.form.get('DeliveryDate'),
                'Agency': request.form.get('Agency'),
                'BillAmount': float(request.form.get('BillAmount', 0)),
                'TaxAmount': float(request.form.get('TaxAmount', 0)),
                'DiscountInBill': request.form.get('DiscountInBill', 'No'),
                'Disc_amount': float(request.form.get('Disc_amount', 0)),
                'BillTotal': float(request.form.get('BillTotal', 0))
            }

            if request.form.get('DiscountInBill') == 'Yes':
                discount_in_bill = 1
                disc_pct = round(bill_data['Disc_amount']/bill_data['BillAmount']*100, 2) if bill_data['BillAmount'] > 0 else 0.0
            
            try:
                date_obj = datetime.strptime(bill_data['BillDate'], '%Y-%m-%d')
                date_formatted = date_obj.strftime('%y%m%d')
                bill_id = str(bill_data['BillNo']) + '-' + date_formatted
                logging.info(f"Generated Bill ID: {bill_id}")
            except ValueError as e:
                flash(f"Invalid date format: {str(e)}", "error")
                return redirect(url_for('inventory.inventory'))
            
            logging.info(f"Bill data extracted - BillNo: {bill_data['BillNo']}, Agency: {bill_data['Agency']}, BillTotal: {bill_data['BillTotal']}")
            
            # Extract items data
            logging.info("Extracting items data from form")
            item_names = request.form.getlist('item_name')
            quantities = request.form.getlist('quantity')
            batch_nos = request.form.getlist('batch_no')
            expiry_dates = request.form.getlist('expiry_date')
            prices = request.form.getlist('price')
            differences = request.form.getlist('difference')
            
            
            logging.info(f"Items extracted - Count: {len(item_names)}")
            
            if not item_names:
                logging.warning("No items provided in the form")
                flash('Please add at least one item', 'error')
                return redirect(url_for('inventory.inventory'))
            
            # Validate bill data
            logging.info("Validating bill data")
            required_fields = ['BillDate', 'BillNo', 'DeliveryDate', 'Agency']
            for field in required_fields:
                if not bill_data[field]:
                    logging.error(f"Required field missing: {field}")
                    flash(f'{field} is required', 'error')
                    return redirect(url_for('inventory.inventory'))
            
            logging.info("Bill data validation successful")
            
            # Check if bill already exists
            logging.info(f"Checking if bill already exists - BillId: {bill_id}")
            check_bill_query = "SELECT BillId FROM DeliveryBills WHERE BillId = ?"
            try:
                check_result = client.execute(check_bill_query, [bill_id])
                if check_result.rows:
                    logging.warning(f"Bill with BillId {bill_id} already exists")
                    flash(f'Bill number {bill_id} already exists', 'error')
                    return redirect(url_for('inventory.inventory'))
            except Exception as check_error:
                logging.error(f"Error checking existing bill: {str(check_error)}")
                # Continue with insertion attempt
            
            

            # Insert bill with enhanced error handling
            logging.info(f"Inserting bill into database - BillId: {bill_id}")
            bill_insert_query = """
            INSERT INTO DeliveryBills (BillDate, BillNo, mAgency, BillAmount, TaxAmount, DiscountInBill, DiscountAmount,DiscountPercent, BillTotal, BillId)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Log the actual values being inserted
            bill_values = [
                bill_data['BillDate'],
                bill_data['BillNo'],
                bill_data['Agency'],
                bill_data['BillAmount'],
                bill_data['TaxAmount'],
                bill_data['DiscountInBill'],
                bill_data['Disc_amount'],
                disc_pct,
                bill_data['BillTotal'],
                bill_id
            ]
            logging.info(f"Bill insert values: {bill_values}")
            
            try:
                bill_result = client.execute(bill_insert_query, bill_values)
                logging.info(f"Bill insert response type: {type(bill_result)}")
                logging.info(f"Bill insert response: {bill_result}")
                logging.info(f"Bill inserted successfully - BillNo: {bill_data['BillNo']}")
            except Exception as bill_insert_error:
                logging.error(f"Database error during bill insertion: {str(bill_insert_error)}")
                logging.error(f"Bill insert query: {bill_insert_query}")
                logging.error(f"Bill insert values: {bill_values}")
                
                # Try to get more details about the error
                error_msg = str(bill_insert_error)
                if "KeyError: 'result'" in error_msg:
                    logging.error("Database client response format error - possible connection or schema issue")
                    flash('Database connection error. Please try again.', 'error')
                elif "UNIQUE constraint" in error_msg:
                    flash(f'Bill number {bill_data["BillNo"]} already exists', 'error')
                else:
                    flash(f'Database error: {error_msg}', 'error')
                
                return redirect(url_for('inventory.inventory'))
            
            
            
            # Insert items with enhanced error handling
            logging.info(f"Starting to insert {len(item_names)} items for BillId: {bill_id}")
            item_insert_query = """
            INSERT INTO StockDeliveries (id, DeliveryDate, MName, DeliveryStock, BatchNo, ExpiryDate, NewMRP, BillId, PriceChange, SaleableStock)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            successful_items = 0
            failed_items = 0
            
            for i in range(len(item_names)):
                item_id = bill_id + '_0' + str(i+1).zfill(2)
                try:
                    # Validate item data before insertion
                    if not item_names[i] or not quantities[i]:
                        logging.warning(f"Skipping item {i+1} due to missing name or quantity")
                        failed_items += 1
                        continue
                    
                    item_values = [
                        item_id, # Use zfill for better formatting
                        bill_data['DeliveryDate'],  
                        item_names[i],
                        int(quantities[i]),
                        batch_nos[i] if batch_nos[i] else '',
                        expiry_dates[i] if expiry_dates[i] else None,
                        float(prices[i]) if prices[i] else 0.0,
                        bill_id,
                        float(differences[i]) if differences and i < len(differences) and differences[i] else 0.0,
                        0
                    ]
                    
                    logging.info(f"Inserting item {i+1}/{len(item_names)}: {item_names[i]}, Values: {item_values}")
                    
                    item_result = client.execute(item_insert_query, item_values)
                    logging.info(f"Item {i+1} insert result: {item_result}")
                    
                    successful_items += 1
                    logging.info(f"Item {i+1} inserted successfully: {item_names[i]}")
                    
                except Exception as item_error:
                    failed_items += 1
                    logging.error(f"Failed to insert item {i+1} ({item_names[i]}): {str(item_error)}")
                    logging.error(f"Item values that failed: {item_values}")
                    continue
            
            logging.info(f"Items insertion completed - Success: {successful_items}, Failed: {failed_items}")
            
            if failed_items > 0:
                flash(f'Purchase saved with warnings. {successful_items} items saved, {failed_items} items failed. Bill ID: {bill_id}', 'warning')
            else:
                flash(f'Purchase saved successfully! Bill ID: {bill_id}', 'success')
            
            logging.info(f"Bill and inventory save process completed successfully - BillId: {bill_id}")
            return redirect(url_for('inventory.inventory'))
            
        except Exception as e:
            logging.error(f"Critical error during bill and inventory save: {str(e)}", exc_info=True)
            flash(f'Error saving purchase: {str(e)}', 'error')
            return redirect(url_for('inventory.inventory'))

# API Routes for AJAX functionality
@inventory_bp.route('/api/medicine-details')
def get_medicine_details():
    """Get medicine details for display in the form"""
    try:
        medicine_name = request.args.get('name')
        if not medicine_name:
            return jsonify({'error': 'Medicine name is required'}), 400
        
        query = """
        SELECT MName, MCompany, Mtype, MRP, PTR, Weight, GST, HSN
        FROM MedicineList 
        WHERE MName = ?
        """
        
        result = client.execute(query, [medicine_name])
        
        if result.rows and len(result.rows) > 0:
            medicine = result.rows[0]
            return jsonify({
                'MName': medicine[0],
                'MCompany': medicine[1],
                'Mtype': medicine[2],
                'MRP': medicine[3],
                'PTR': medicine[4],
                'Weight': medicine[5],
                'GST': medicine[6],
                'HSN': medicine[7]
            })
        else:
            return jsonify({'error': 'Medicine not found'}), 404
            
    except Exception as e:
        logging.error(f"Error getting medicine details: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/api/medicine-types')
def get_medicine_types():
    """Get available medicine types with next available IDs"""
    try:
        # Get all medicine types
        type_query = "SELECT DISTINCT Mtype FROM MedicineList WHERE Mtype IS NOT NULL ORDER BY Mtype"
        type_result = client.execute(type_query)
        
        types_data = []
        for row in type_result.rows:
            mtype = row[0]
            
            # Get the next available ID for this type
            next_id_query = """
            SELECT COALESCE(MAX(CAST(SUBSTR(MId, LENGTH(?) + 1) AS INTEGER)), 0) + 1 as next_id
            FROM MedicineList 
            WHERE MId LIKE ? || '%'
            """
            
            # Get the first 3 characters of the type for the prefix
            type_prefix = mtype[:3].upper()
            pattern = type_prefix
            
            next_id_result = client.execute(next_id_query, [type_prefix, pattern])
            next_id = next_id_result.rows[0][0] if next_id_result.rows else 1
            
            types_data.append({
                'type': mtype,
                'prefix': type_prefix,
                'next_id': f"{type_prefix}{next_id:03d}"
            })
        
        return jsonify({'success': True, 'types': types_data})
        
    except Exception as e:
        logging.error(f"Error getting medicine types: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/api/add-medicine', methods=['POST'])
def add_medicine():
    """Add new medicine to the database"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('MName') or not data.get('Mtype'):
            return jsonify({'success': False, 'error': 'Medicine name and type are required'}), 400
        
        # Generate MId based on type
        mtype = data['Mtype']
        type_prefix = mtype[:3].upper()
        
        # Get next available ID
        next_id_query = """
        SELECT COALESCE(MAX(CAST(SUBSTR(MId, LENGTH(?) + 1) AS INTEGER)), 0) + 1 as next_id
        FROM MedicineList 
        WHERE MId LIKE ? || '%'
        """
        
        next_id_result = client.execute(next_id_query, [type_prefix, type_prefix])
        next_id = next_id_result.rows[0][0] if next_id_result.rows else 1
        medicine_id = f"{type_prefix}{next_id:03d}"
        
        # Insert new medicine
        insert_query = """
        INSERT INTO MedicineList (MId, MName, MCompany, Mtype, MRP, PTR, Weight, GST, HSN, offer1, offer2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        client.execute(insert_query, [
            medicine_id,
            data['MName'],
            data.get('MCompany', ''),
            data['Mtype'],
            float(data.get('MRP', 0)) if data.get('MRP') else None,
            float(data.get('PTR', 0)) if data.get('PTR') else None,
            data.get('Weight', ''),
            float(data.get('GST', 0)) if data.get('GST') else None,
            data.get('HSN', ''),
            data.get('Offer1', ''),
            data.get('Offer2', '')

        ])
        
        return jsonify({
            'success': True, 
            'message': 'Medicine added successfully',
            'medicine_id': medicine_id
        })
        
    except Exception as e:
        logging.error(f"Error adding medicine: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/update-price', methods=['POST'])
def update_price():
    """Update medicine price"""
    try:
        medicine_name = request.form.get('medicine_name')
        new_mrp = request.form.get('new_mrp')
        new_ptr = request.form.get('new_ptr')
        old_mrp = request.form.get('old_mrp')
        old_ptr = request.form.get('old_ptr')
        
        if not medicine_name or not new_mrp:
            flash('Medicine name and new MRP are required', 'error')
            return redirect(url_for('inventory.inventory'))
        
        # Update the medicine
        update_query = """
        UPDATE MedicineList 
        SET MRP = ?, PTR = ?
        WHERE MName = ?
        """
        
        client.execute(update_query, [
            float(new_mrp),
            float(new_ptr) if new_ptr else None,
            medicine_name
        ])
        
        # Log the price change
        logging.info(f"Price updated for {medicine_name}: MRP {old_mrp} -> {new_mrp}, PTR {old_ptr} -> {new_ptr}")
        
        flash(f'Price updated successfully for {medicine_name}', 'success')
        return redirect(url_for('inventory.inventory'))
        
    except Exception as e:
        logging.error(f"Error updating price: {e}")
        flash(f'Error updating price: {str(e)}', 'error')
        return redirect(url_for('inventory.inventory'))