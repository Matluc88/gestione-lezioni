# Timezone Fix Documentation

## Problem Description
Users reported that selecting June 10th in the lesson creation calendar was displaying as June 9th due to timezone conversion issues in the JavaScript code.

## Root Cause
The original code in `templates/aggiungi_lezione.html` was using `date.toISOString().split('T')[0]` which converts dates to UTC timezone, causing a shift of one day in certain timezones.

## Solution Implemented
Replaced UTC date conversion with local timezone formatting in the Flatpickr `onClose` function:

```javascript
// OLD CODE (problematic):
const formattedDate = date.toISOString().split('T')[0];

// NEW CODE (fixed):
const year = date.getFullYear();
const month = String(date.getMonth() + 1).padStart(2, '0');
const day = String(date.getDate()).padStart(2, '0');
const formattedDate = `${year}-${month}-${day}`;
```

## Verification Steps
1. Navigate to `/aggiungi_lezione` page
2. Click "SELEZIONA DATE DAL CALENDARIO" button
3. Select June 10th from the calendar
4. Close the calendar (press Escape or click outside)
5. Verify the selected date displays as "mar 10 giu 2025" (not "lun 9 giu 2025")

## Troubleshooting
If you still see the old behavior (June 10th showing as June 9th):

### 1. Clear Browser Cache
- **Chrome/Edge**: Ctrl+Shift+Delete → Clear browsing data → Cached images and files
- **Firefox**: Ctrl+Shift+Delete → Cache
- **Safari**: Cmd+Option+E → Empty Caches

### 2. Hard Refresh
- **Windows**: Ctrl+F5 or Ctrl+Shift+R
- **Mac**: Cmd+Shift+R

### 3. Test in Incognito/Private Mode
- Open a new incognito/private browser window
- Navigate to the application
- Test the date selection functionality

### 4. Check Browser Developer Tools
1. Open Developer Tools (F12)
2. Go to Network tab
3. Check "Disable cache" option
4. Refresh the page
5. Test date selection

### 5. Verify JavaScript Console
1. Open Developer Tools (F12)
2. Go to Console tab
3. Look for any JavaScript errors
4. Test date selection and check for error messages

## Technical Details
- **File Modified**: `templates/aggiungi_lezione.html`
- **Function**: Flatpickr `onClose` callback (lines 148-152)
- **PR**: #22 - "Fix timezone bug in date selection"
- **Commit**: 2ecfeae - "Fix timezone bug in date selection - use local timezone instead of UTC"

## Additional Date Handling
The application also uses `toLocaleDateString('it-IT')` in the `aggiornaListaDate()` function for displaying selected dates, which correctly handles timezone formatting for Italian locale.

## Testing Confirmation
✅ Local testing confirms the fix is working correctly
✅ June 10th selection displays as "mar 10 giu 2025"
✅ No timezone shift occurs
✅ Multiple date selections work properly
