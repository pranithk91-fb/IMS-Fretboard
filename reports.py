import pandas as pd
from flask import Blueprint, render_template, request
from db_connect import client

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/', methods=['GET'])
def reports():
    try:
        # Get all stock data as pandas DataFrame
        query = """
        SELECT 
            MName,
            CurrentStock,
            MType,
            LastDeliveryDate,
            ClosestToExpiry,
            MCompany,
            CASE 
                WHEN ClosestToExpiry = 'No info' THEN NULL
                ELSE CAST((julianday(date(substr(ClosestToExpiry, 1, 4) || '-' || substr(ClosestToExpiry, 6, 2) || '-30')) - julianday('now')) AS INTEGER)
            END AS DaysToExpiry
        FROM vw_CurrentStocks 
        ORDER BY MName
        """
        
        # Load data into pandas DataFrame
        stock_result = client.execute(query)

        
        
        if stock_result:
            df = pd.DataFrame(stock_result.rows, columns=[
                'MName', 'CurrentStock', 'MType', 'LastDeliveryDate', 
                'ClosestToExpiry', 'MCompany', 'DaysToExpiry'
            ])
            
            # Convert data types and handle missing values
            df['CurrentStock'] = pd.to_numeric(df['CurrentStock'], errors='coerce').fillna(0)
            df['DaysToExpiry'] = pd.to_numeric(df['DaysToExpiry'], errors='coerce')
            
            # Fill NaN values
            df['MType'] = df['MType'].fillna('Unknown')
            df['MCompany'] = df['MCompany'].fillna('Unknown')
            df['LastDeliveryDate'] = df['LastDeliveryDate'].fillna('No delivery')
            df['ClosestToExpiry'] = df['ClosestToExpiry'].fillna('No info')
            
        else:
            # Create empty DataFrame with proper columns
            df = pd.DataFrame(columns=[
                'MName', 'CurrentStock', 'MType', 'LastDeliveryDate', 
                'ClosestToExpiry', 'MCompany', 'DaysToExpiry'
            ])
        
        # Get filter options using pandas
        medicine_list = sorted(df['MName'].dropna().unique().tolist()) if not df.empty else []
        type_list = sorted(df['MType'].dropna().unique().tolist()) if not df.empty else []
        company_list = sorted(df['MCompany'].dropna().unique().tolist()) if not df.empty else []
        
        # Apply filters
        filtered_df = df.copy()
        medicine_filter = request.args.get('medicine_filter', '')
        type_filter = request.args.get('type_filter', '')
        company_filter = request.args.get('company_filter', '')
        
        if medicine_filter:
            filtered_df = filtered_df[filtered_df['MName'] == medicine_filter]
        if type_filter:
            filtered_df = filtered_df[filtered_df['MType'] == type_filter]
        if company_filter:
            filtered_df = filtered_df[filtered_df['MCompany'] == company_filter]
        
        # Calculate statistics using pandas
        total_medicines = len(filtered_df)
        if not filtered_df.empty:
            # For tablets: low stock < 100, for others: low stock < 10
            tablets_low = ((filtered_df['MType'] == 'Tablets') & (filtered_df['CurrentStock'] < 100)).sum()
            others_low = ((filtered_df['MType'] != 'Tablets') & (filtered_df['CurrentStock'] < 10)).sum()
            low_stock_count = int(tablets_low + others_low)
        else:
            low_stock_count = 0
            
        near_expiry_count = int((filtered_df['DaysToExpiry'] < 30).sum()) if not filtered_df.empty else 0
        
        # Convert back to list of dicts for template
        stock_data = filtered_df.to_dict('records') if not filtered_df.empty else []
        
        return render_template('reports.html',
                             stock_data=stock_data,
                             medicine_list=medicine_list,
                             type_list=type_list,
                             company_list=company_list,
                             selected_medicine=medicine_filter,
                             selected_type=type_filter,
                             selected_company=company_filter,
                             total_medicines=total_medicines,
                             low_stock_count=low_stock_count,
                             near_expiry_count=near_expiry_count,
                             active_page='reports')
        
    except Exception as e:
        print(f"Reports error: {e}")
        return render_template('reports.html',
                             stock_data=[],
                             medicine_list=[],
                             type_list=[],
                             company_list=[],
                             selected_medicine='',
                             selected_type='',
                             selected_company='',
                             total_medicines=0,
                             low_stock_count=0,
                             near_expiry_count=0,
                             active_page='reports')