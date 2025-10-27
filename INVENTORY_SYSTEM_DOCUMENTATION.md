# Inventory Management System - Documentation

## Overview
The Inventory Management System (IMS) is a Flask-based web application for managing medical inventory purchases. It allows users to create purchase bills with multiple items and automatically calculates price differences against standard MRP values.

## System Architecture

### Technology Stack
- **Backend**: Flask (Python)
- **Database**: Cassandra
- **Frontend**: HTML, CSS, JavaScript, jQuery
- **UI Components**: Select2 (searchable dropdowns)

### Key Files
- `app.py` - Main Flask application
- `inventory.py` - Inventory module with routes and business logic
- `templates/inventory.html` - Main inventory entry page
- `static/style.css` - Styling
- `db_connect.py` - Database connection module

## Database Schema

### Tables Used

#### 1. DeliveryBills
Stores bill header information:
- `BillNo` - Bill number
- `BillDate` - Bill date
- `MAgency` - Agency name
- `BillAmount` - Bill amount (excluding tax)
- `TaxAmount` - Tax amount
- `BillTotal` - Total amount (Bill + Tax)
- `DiscountInBill` - Discount flag (1/0)
- `DiscountPercent` - Discount percentage
- `BillId` - Generated unique ID (BillNo-YYMMDD)

#### 2. stockdeliveries
Stores individual item details:
- `Id` - Unique item ID (BillId_0X format)
- `DeliveryDate` - Delivery date
- `Mname` - Medicine/item name
- `DeliveryStock` - Quantity delivered
- `PriceChange` - Price difference from MRP
- `NewMRP` - Actual price paid
- `ExpiryDate` - Expiry date (Month/Year format)
- `BatchNo` - Batch number
- `BillId` - Reference to bill
- `SaleableStock` - Always set to 0

#### 3. medicinelist
Master data for medicines:
- `MName` - Medicine name
- `MCompany` - Company name
- `Mtype` - Medicine type
- `MRP` - Maximum Retail Price
- `GST` - GST percentage
- `HSN` - HSN code
- `PTR` - Price to Retailer
- `Offer1`, `Offer2` - Offer details
- `Weight` - Weight/quantity

#### 4. mAgencies
Master data for agencies:
- `AgencyName` - Name of the agency

## User Interface

### Page Sections

#### 1. Bill Details Section
- **Bill Date**: Date of the bill
- **Bill No**: Unique bill number
- **Delivery Date**: Expected delivery date
- **Agency**: Select from dropdown (searchable)
- **Bill Amount**: Total bill amount (excluding tax)
- **Tax Amount**: Tax amount
- **Discount**: Yes/No selection
- **Discount %**: Discount percentage
- **Final Amount**: Auto-calculated total

#### 2. Items Entry Section
- **Item Name**: Searchable dropdown with Select2
- **Quantity**: Number of items
- **Batch No**: Batch number
- **Expiry Date**: Month/Year picker
- **Price**: Actual price paid
- **Add Another Item**: Button to add item to table

#### 3. Items Table
- Displays all added items
- Shows price difference from MRP
- Remove button (×) for each item
- Hidden form fields for data submission

### Features

#### Item Details Display
When an item is selected, the system displays:
- **Row 1**: Weight, MRP, GST, Offers
- **Row 2**: Company, Type, HSN, PTR

#### Price Difference Calculation
- Automatically calculates difference between entered price and MRP
- Shows positive/negative difference
- Stores difference for analysis

#### Form Validation
- All required fields must be filled
- Numeric validation for amounts
- Date validation for dates

## User Workflow

### Adding a Purchase Entry

1. **Fill Bill Details**:
   ```
   - Enter bill date, number, delivery date
   - Select agency from dropdown
   - Enter bill amount, tax amount
   - Select discount option and percentage
   ```

2. **Add Items**:
   ```
   - Select item from searchable dropdown
   - Review displayed item details (MRP, company, etc.)
   - Enter quantity, batch number, expiry date
   - Enter actual price paid
   - Click "Add Another Item"
   - Repeat for all items
   ```

3. **Review and Submit**:
   ```
   - Review items in the table
   - Check price differences
   - Remove any incorrect items using × button
   - Click "Save Purchase"
   ```

4. **Confirmation**:
   ```
   - System displays "Inventory purchase saved!" message
   - Data is saved to database tables
   ```

## API Endpoints

### `/inventory` (GET)
- Displays the inventory entry form
- Loads medicine and agency dropdowns
- Handles user authentication

### `/inventory` (POST)
- Processes form submission
- Validates and saves data
- Returns success/error message

### `/api/medicine-details` (GET)
- AJAX endpoint for item details
- Parameter: `name` (medicine name)
- Returns: JSON with medicine details

## Security Features

### User Authentication
- Session-based authentication
- Allowed users: `pranith`, `preethi`
- 403 Forbidden for unauthorized access

### Input Validation
- Server-side validation for all inputs
- SQL injection protection via parameterized queries
- XSS protection through proper escaping

## Error Handling

### Common Issues and Solutions

#### 1. "Please fill out fields" Error
- **Cause**: Required fields not filled or form structure issue
- **Solution**: Ensure all bill details and at least one item is added

#### 2. Item Details Not Loading
- **Cause**: AJAX call failure or medicine not in database
- **Solution**: Check network tab in browser dev tools, verify medicine exists

#### 3. Database Connection Issues
- **Cause**: Cassandra connection problems
- **Solution**: Check `db_connect.py` configuration and database status

#### 4. Items Not Saving
- **Cause**: Form structure or JavaScript issues
- **Solution**: Check browser console for errors, verify hidden inputs in table

## Development Guidelines

### Code Structure
```
IMS_2024/
├── app.py                 # Main Flask app
├── inventory.py           # Inventory module
├── db_connect.py          # Database connection
├── templates/
│   ├── base.html         # Base template
│   └── inventory.html    # Inventory page
├── static/
│   ├── style.css         # Main styles
│   └── login_style.css   # Login styles
└── requirements.txt       # Dependencies
```

### Adding New Features

#### Adding New Fields
1. Update database schema
2. Add form fields in HTML
3. Update Python form processing
4. Add validation rules

#### Modifying Item Details
1. Update `medicinelist` table structure
2. Modify `/api/medicine-details` endpoint
3. Update JavaScript item details display

### Testing Guidelines

#### Manual Testing Checklist
- [ ] User authentication works
- [ ] All dropdowns load properly
- [ ] Item details display correctly
- [ ] Price calculations are accurate
- [ ] Form validation prevents invalid submissions
- [ ] Data saves correctly to database
- [ ] Success message appears after submission

#### Browser Compatibility
- Chrome (recommended)
- Firefox
- Edge
- Safari (limited testing)

## Maintenance

### Regular Tasks
1. **Database Backup**: Regular backups of Cassandra data
2. **Log Monitoring**: Check application logs for errors
3. **Performance**: Monitor query performance
4. **Security Updates**: Keep dependencies updated

### Troubleshooting

#### Debug Mode
Enable debug prints in `inventory.py`:
```python
print("=== FORM DATA RECEIVED ===")
print("request.form:", dict(request.form))
```

#### Browser Developer Tools
- **F12** → Elements: Check HTML structure
- **F12** → Console: Check JavaScript errors
- **F12** → Network: Check AJAX requests

## Deployment

### Prerequisites
- Python 3.7+
- Cassandra database
- Required Python packages (see requirements.txt)

### Environment Setup
```bash
pip install -r requirements.txt
export FLASK_APP=app.py
export FLASK_ENV=development  # for development
python app.py
```

### Production Considerations
- Use production WSGI server (Gunicorn, uWSGI)
- Configure proper logging
- Set up SSL/HTTPS
- Implement proper session management
- Database connection pooling

## Support

### Contact Information
- **Development Team**: [Your Team Contact]
- **System Admin**: [Admin Contact]
- **Database Admin**: [DBA Contact]

### Documentation Updates
This documentation should be updated when:
- New features are added
- Database schema changes
- UI/UX modifications
- Bug fixes that affect workflow

---

*Last Updated: October 2025*
*Version: 1.0*