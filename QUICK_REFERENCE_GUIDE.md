# Inventory System - Quick Reference Guide

## 🚀 Getting Started

### Access the System
1. Navigate to: `http://localhost:5000/inventory`
2. Login with authorized credentials
3. Start adding inventory purchases

### Basic Workflow
```
Bill Details → Add Items → Review Table → Save Purchase
```

## 📝 Step-by-Step Process

### 1. Fill Bill Details
| Field | Description | Required | Format |
|-------|-------------|----------|--------|
| Bill Date | Date of bill | ✅ | YYYY-MM-DD |
| Bill No | Unique bill number | ✅ | Text |
| Delivery Date | Expected delivery | ✅ | YYYY-MM-DD |
| Agency | Supplier agency | ✅ | Select from dropdown |
| Bill Amount | Amount (ex-tax) | ✅ | Number |
| Tax Amount | Tax component | ✅ | Number |
| Discount | Discount given? | ✅ | Yes/No |
| Discount % | Discount percentage | ✅ | Number |

### 2. Add Items to Purchase
1. **Select Item**: Use searchable dropdown
2. **Review Details**: System shows MRP, company, etc.
3. **Fill Details**:
   - Quantity (number of units)
   - Batch Number
   - Expiry Date (Month/Year only)
   - Actual Price Paid
4. **Click "Add Another Item"**
5. **Repeat** for all items

### 3. Review & Submit
- Check items in table below
- Verify price differences
- Remove incorrect items using ❌ button
- Click **"Save Purchase"**

## 💡 Key Features

### 🔍 Smart Item Search
- Type to search medicine names
- Auto-complete functionality
- Displays item details instantly

### 💰 Price Tracking
- Shows MRP vs actual price
- Calculates differences automatically
- Helps identify cost savings/overruns

### 📊 Item Information Display
**When item selected, shows:**
- Weight, MRP, GST, Offers
- Company, Type, HSN, PTR codes

### ✅ Data Validation
- Prevents duplicate submissions
- Validates all required fields
- Ensures data integrity

## ⚠️ Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Fill out fields" error | Ensure all bill details filled + at least 1 item added |
| Item details not showing | Check medicine exists in database |
| Can't submit form | Check browser console for errors (F12) |
| Select2 not working | Refresh page, check JavaScript errors |

## 🛠️ Troubleshooting

### Quick Debug Steps
1. **Press F12** → Console tab
2. Look for JavaScript errors (red text)
3. Check Network tab for failed requests
4. Verify data in Elements tab

### Form Issues
- Ensure items are added to table (not just filled in form)
- Check hidden inputs exist in table HTML
- Verify form boundaries include table

## 📱 Browser Compatibility
- ✅ **Chrome** (Recommended)
- ✅ **Firefox**
- ✅ **Edge**
- ⚠️ **Safari** (Limited)

## 🔒 Security Notes
- Only authorized users can access
- Session-based authentication
- All data validated server-side

## 📞 Need Help?

### For Technical Issues
- Check browser console (F12)
- Try refreshing the page
- Contact development team

### For Data Issues
- Verify medicine exists in master data
- Check agency spelling
- Contact system administrator

---

**💡 Pro Tips:**
- Use Ctrl+F to quickly find medicines
- Double-check expiry dates (MM/YYYY format)
- Review price differences before submitting
- Keep batch numbers accurate for tracking

*Quick Reference v1.0 - October 2025*