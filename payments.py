from flask import Blueprint, render_template, request, session, abort, jsonify
from db_connect import client
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)

payments_bp = Blueprint('payments', __name__, template_folder='templates')

@payments_bp.route('/payments', methods=['GET', 'POST'])
def payments():
    """Payments management page - shows unpaid bills with filtering options"""
    allowed_users = {'pranith', 'preethi'}
    username = session.get('username')

    if username not in allowed_users:
        abort(403)  # Forbidden access

    # Get filter parameters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    agency_filter = request.args.get('agency', '')
    payment_status = request.args.get('payment_status', 'Unpaid')  # Default to unpaid

    # Build the query with filters
    base_query = """
        SELECT 
            BillId,
            BillNo,
            BillDate,
            MAgency,
            BillAmount,
            TaxAmount,
            BillTotal,
            DiscountInBill,
            DiscountAmount,
            DiscountPercent,
            BillPaymentStatus,
            BillPaymentDate,
            PaymentMode,
            AmountPaid,
            TransactionDetails
        FROM DeliveryBills 
        WHERE 1=1
    """
    
    params = []
    
    # Add payment status filter
    if payment_status and payment_status != 'all':
        # Handle case sensitivity - convert both to lowercase for comparison
        base_query += " AND (lower(BillPaymentStatus) = ? OR BillPaymentStatus IS NULL)"
        params.append(payment_status.lower())
    
    # Add date filters
    if date_from:
        base_query += " AND BillDate >= ?"
        params.append(date_from)
    
    if date_to:
        base_query += " AND BillDate <= ?"
        params.append(date_to)
    
    # Add agency filter
    if agency_filter:
        base_query += " AND MAgency = ?"
        params.append(agency_filter)
    
    # Order by date (newest first), then by BillId
    base_query += " ORDER BY BillDate DESC, BillId DESC"
    

    
    try:
        # Execute query
        result = client.execute(base_query, params)
        

        
        bills = []
        
        for row in result.rows:
            bills.append({
                'BillId': row[0],
                'BillNo': row[1],
                'BillDate': row[2],
                'MAgency': row[3],
                'BillAmount': float(row[4]) if row[4] else 0,
                'TaxAmount': float(row[5]) if row[5] else 0,
                'BillTotal': float(row[6]) if row[6] else 0,
                'DiscountInBill': row[7],
                'DiscountAmount': float(row[8]) if row[8] else 0,
                'DiscountPercent': float(row[9]) if row[9] else 0,
                'BillPaymentStatus': row[10] or 'unpaid',
                'PaymentDate': row[11],
                'PaymentMode': row[12],
                'AmountPaid': float(row[13]) if row[13] else 0,
                'TransactionDetails': row[14] or ''
            })
        

        
        # Get list of agencies for filter dropdown from mAgencies table
        agencies_query = "SELECT AgencyName FROM mAgencies ORDER BY AgencyName"
        agency_result = client.execute(agencies_query)
        agencies = [row[0] for row in agency_result.rows if row[0]]
        
        # Calculate summary statistics
        total_bills = len(bills)
        total_amount = sum(bill['BillTotal'] for bill in bills)
        
        # Calculate paid and unpaid totals
        paid_amount = sum(bill['BillTotal'] for bill in bills if (bill['BillPaymentStatus'] or '').lower() in ['paid', 'Paid'])
        unpaid_amount = sum(bill['BillTotal'] for bill in bills if (bill['BillPaymentStatus'] or '').lower() in ['unpaid', 'Unpaid', ''] or bill['BillPaymentStatus'] is None)
        
        logging.info(f"Payments page accessed by {username}. Processed {total_bills} bills from {len(agencies)} agencies.")
        
        return render_template(
            'payments.html', 
            bills=bills,
            agencies=agencies,
            total_bills=total_bills,
            total_amount=total_amount,
            paid_amount=paid_amount,
            unpaid_amount=unpaid_amount,
            active_page='payments',
            # Pass current filters back to template
            current_filters={
                'date_from': date_from,
                'date_to': date_to,
                'agency': agency_filter,
                'payment_status': payment_status
            }
        )
        
    except Exception as e:
        logging.error(f"Error fetching bills for payments page: {str(e)}")
        return render_template(
            'payments.html', 
            bills=[],
            agencies=[],
            total_bills=0,
            total_amount=0,
            paid_amount=0,
            unpaid_amount=0,
            active_page='payments',
            error=f"Error loading bills: {str(e)}",
            current_filters={
                'date_from': date_from,
                'date_to': date_to,
                'agency': agency_filter,
                'payment_status': payment_status
            }
        )

@payments_bp.route('/api/bulk-payment-update', methods=['POST'])
def bulk_payment_update():
    """Update payment details for multiple bills"""
    allowed_users = {'pranith', 'preethi'}
    username = session.get('username')

    if username not in allowed_users:
        return jsonify({"error": "Unauthorized access"}), 403

    try:
        data = request.get_json()
        bill_ids = data.get('bill_ids', [])
        bill_data = data.get('bills_data', [])
        payment_date = data.get('payment_date')
        payment_mode = data.get('payment_mode')
        amount_paid = data.get('amount_paid', 0)
        transaction_details = data.get('transaction_details', '')
        selected_total = data.get('selected_total', 0)
        original_total = data.get('original_total', 0)
        discount_amount = data.get('discount_amount', 0)
        discount_percentage = data.get('discount_percentage', 0)
        
        logging.info(f"Bulk payment update request: {len(bill_ids)} bills, discount: ₹{discount_amount}")
        
        if not bill_ids or not payment_date or not payment_mode:
            return jsonify({"error": "Bill IDs, payment date, and payment mode are required"}), 400
        
        # Validate and ensure payment date is in YYYY-MM-DD format
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(payment_date, '%Y-%m-%d')
            formatted_payment_date = parsed_date.strftime('%Y-%m-%d')
        except ValueError as e:
            return jsonify({"error": f"Invalid date format: {payment_date}. Expected YYYY-MM-DD"}), 400
        
        payment_status = 'Paid'
        updated_count = 0
        
        # Create a dictionary for quick bill data lookup
        bill_data_dict = {bill['billId']: bill for bill in bill_data} if bill_data else {}
        
        # Calculate final amounts properly for each bill
        def calculate_final_amount(bill_info, total_discount_percentage):
            """Calculate the final amount for a bill after applying discount"""
            try:
                # Get the original bill total
                original_amount = float(bill_info.get('billTotal', 0))
                
                # Check if bill already has a discount
                existing_discount = float(bill_info.get('discountAmount', 0))
                
                # Calculate the amount eligible for discount
                # If bill already has discount, apply new discount to original amount
                base_amount = original_amount
                
                # Apply the payment discount
                payment_discount = (base_amount * total_discount_percentage / 100) if total_discount_percentage > 0 else 0
                
                # Final amount = original amount - payment discount
                final_amount = original_amount - payment_discount
                
                # Ensure final amount is not negative
                final_amount = max(0, final_amount)
                
                return {
                    'originalAmount': original_amount,
                    'paymentDiscount': payment_discount,
                    'finalAmount': final_amount,
                    'hadExistingDiscount': existing_discount > 0,
                    'existingDiscount': existing_discount
                }
            except (ValueError, TypeError) as e:
                logging.error(f"Error calculating final amount for bill {bill_info.get('billId')}: {e}")
                return {
                    'originalAmount': 0,
                    'paymentDiscount': 0,
                    'finalAmount': 0,
                    'hadExistingDiscount': False,
                    'existingDiscount': 0
                }
        
        # Recalculate final amounts for all bills
        processed_bills = []
        total_final_amount = 0
        
        for bill_id in bill_ids:
            bill_info = bill_data_dict.get(bill_id)
            if bill_info:
                calc_result = calculate_final_amount(bill_info, discount_percentage)
                processed_bills.append({
                    'billId': bill_id,
                    'originalAmount': calc_result['originalAmount'],
                    'paymentDiscount': calc_result['paymentDiscount'],
                    'finalAmount': calc_result['finalAmount'],
                    'hadExistingDiscount': calc_result['hadExistingDiscount'],
                    'existingDiscount': calc_result['existingDiscount']
                })
                total_final_amount += calc_result['finalAmount']
            else:
                # If no bill data, use equal distribution
                equal_share = selected_total / len(bill_ids) if bill_ids else 0
                processed_bills.append({
                    'billId': bill_id,
                    'originalAmount': equal_share,
                    'paymentDiscount': 0,
                    'finalAmount': equal_share,
                    'hadExistingDiscount': False,
                    'existingDiscount': 0
                })
                total_final_amount += equal_share
        
        logging.info(f"Calculated total final amount: ₹{total_final_amount:.2f}")
        
        # Update each selected bill
        for processed_bill in processed_bills:
            try:
                bill_id = processed_bill['billId']
                
                # Calculate proportional amount paid for this specific bill
                if total_final_amount > 0:
                    bill_proportion = processed_bill['finalAmount'] / total_final_amount
                    bill_amount_paid = amount_paid * bill_proportion
                else:
                    bill_amount_paid = amount_paid / len(bill_ids) if bill_ids else amount_paid
                
                # Create detailed transaction details
                bill_transaction_details = transaction_details
                if processed_bill['paymentDiscount'] > 0:
                    discount_info = f" | Payment Discount: ₹{processed_bill['paymentDiscount']:.2f}"
                    if processed_bill['hadExistingDiscount']:
                        discount_info += f" (Additional to existing ₹{processed_bill['existingDiscount']:.2f})"
                    bill_transaction_details += discount_info
                
                # Update the database
                client.execute("""
                    UPDATE DeliveryBills 
                    SET BillPaymentStatus = ?, 
                        BillPaymentDate = ?, 
                        PaymentMode = ?,
                        AmountPaid = ?,
                        TransactionDetails = ?
                    WHERE BillId = ?
                """, [payment_status, formatted_payment_date, payment_mode, bill_amount_paid, bill_transaction_details, bill_id])
                
                updated_count += 1
                logging.info(f"Updated bill {bill_id}: Amount paid ₹{bill_amount_paid:.2f}, Discount ₹{processed_bill['paymentDiscount']:.2f}")
                
            except Exception as e:
                logging.error(f"Error updating bill {bill_id}: {str(e)}")
                continue
        
        logging.info(f"Bulk payment update completed: {updated_count} bills updated by {username}")
        
        success_message = f"Payment processed for {updated_count} bills"
        if discount_amount > 0:
            success_message += f" with ₹{discount_amount:.2f} total discount ({discount_percentage}%)"
        
        return jsonify({
            "success": True, 
            "message": success_message,
            "updated_count": updated_count,
            "payment_status": payment_status,
            "total_discount_applied": discount_amount,
            "original_total": original_total,
            "final_total": total_final_amount,
            "processed_bills": processed_bills  # For debugging
        })
        
    except Exception as e:
        logging.error(f"Error in bulk payment update: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to process payment"}), 500

@payments_bp.route('/api/update-payment-status', methods=['POST'])
def update_payment_status():
    """Update payment status for a single bill (legacy endpoint)"""
    allowed_users = {'pranith', 'preethi'}
    username = session.get('username')

    if username not in allowed_users:
        return jsonify({"error": "Unauthorized access"}), 403

    try:
        data = request.get_json()
        bill_id = data.get('bill_id')
        payment_status = data.get('payment_status')
        payment_mode = data.get('payment_mode', '')
        
        if not bill_id or not payment_status:
            return jsonify({"error": "Bill ID and payment status are required"}), 400
        
        # Set payment date if marking as paid
        payment_date = datetime.now().strftime('%Y-%m-%d') if payment_status == 'paid' else None
        
        # Update the bill payment status
        client.execute("""
            UPDATE DeliveryBills 
            SET BillPaymentStatus = ?, 
                BillPaymentDate = ?, 
                PaymentMode = ?
            WHERE BillId = ?
        """, [payment_status, payment_date, payment_mode, bill_id])
        
        logging.info(f"Payment status updated for bill {bill_id} to {payment_status} by {username}")
        
        return jsonify({
            "success": True, 
            "message": f"Payment status updated to {payment_status}",
            "payment_date": payment_date
        })
        
    except Exception as e:
        logging.error(f"Error updating payment status: {str(e)}")
        return jsonify({"error": "Failed to update payment status"}), 500