#!/usr/bin/env python3
"""
Analyze the data structure differences between Python service output and expected Univer format
"""
import json

# Load the API response
with open('api_response.json', 'r') as f:
    api_response = json.load(f)

# Extract the workbook data
workbook_data = api_response.get('data', {})

print("=== PYTHON SERVICE OUTPUT STRUCTURE ANALYSIS ===\n")

# 1. Top-level structure
print("1. Top-level keys:")
for key in workbook_data.keys():
    print(f"   - {key}: {type(workbook_data[key]).__name__}")

# 2. Sheet structure
print("\n2. Sheet structure:")
sheets = workbook_data.get('sheets', {})
for sheet_id, sheet in sheets.items():
    print(f"\n   Sheet ID: {sheet_id}")
    print(f"   Sheet keys: {list(sheet.keys())}")
    
    # Check cellData structure
    cell_data = sheet.get('cellData', {})
    if cell_data:
        first_row_key = list(cell_data.keys())[0]
        first_row = cell_data[first_row_key]
        print(f"   cellData structure:")
        print(f"     - First row key: {first_row_key} (type: {type(first_row_key).__name__})")
        print(f"     - First row type: {type(first_row).__name__}")
        
        if isinstance(first_row, dict) and first_row:
            first_col_key = list(first_row.keys())[0]
            first_cell = first_row[first_col_key]
            print(f"     - First column key: {first_col_key} (type: {type(first_col_key).__name__})")
            print(f"     - First cell keys: {list(first_cell.keys())}")
            print(f"     - First cell value: {first_cell.get('v')}")

# 3. Check for critical Univer requirements
print("\n3. Univer requirements check:")

# Check if sheet IDs match sheetOrder
sheet_ids = set(sheets.keys())
sheet_order = set(workbook_data.get('sheetOrder', []))
print(f"   ✓ Sheet IDs match sheetOrder: {sheet_ids == sheet_order}")

# Check if all cells have required 'v' and 't' keys
print("\n   Cell structure validation:")
valid_cells = 0
invalid_cells = 0
missing_v = 0
missing_t = 0

for sheet_id, sheet in sheets.items():
    cell_data = sheet.get('cellData', {})
    for row_key, row_data in cell_data.items():
        if isinstance(row_data, dict):
            for col_key, cell in row_data.items():
                if 'v' in cell and 't' in cell:
                    valid_cells += 1
                else:
                    invalid_cells += 1
                    if 'v' not in cell:
                        missing_v += 1
                    if 't' not in cell:
                        missing_t += 1

print(f"   ✓ Valid cells: {valid_cells}")
print(f"   ✗ Invalid cells: {invalid_cells}")
if invalid_cells > 0:
    print(f"     - Missing 'v': {missing_v}")
    print(f"     - Missing 't': {missing_t}")

# 4. Check styles
print("\n4. Styles structure:")
styles = workbook_data.get('styles', {})
print(f"   Total styles: {len(styles)}")
if styles:
    first_style_id = list(styles.keys())[0]
    first_style = styles[first_style_id]
    print(f"   First style ID: {first_style_id}")
    print(f"   First style keys: {list(first_style.keys())}")

# 5. Check for required Univer properties
print("\n5. Required Univer properties:")
required_props = ['id', 'name', 'locale', 'styles', 'sheets', 'sheetOrder']
for prop in required_props:
    exists = prop in workbook_data
    print(f"   {'✓' if exists else '✗'} {prop}: {exists}")

# 6. Data integrity check
print("\n6. Data integrity:")
total_cells = sum(
    len(row_data) 
    for sheet in sheets.values() 
    for row_data in sheet.get('cellData', {}).values() 
    if isinstance(row_data, dict)
)
print(f"   Total cells across all sheets: {total_cells}")

# Count cells with actual values
cells_with_values = 0
for sheet in sheets.values():
    cell_data = sheet.get('cellData', {})
    for row_data in cell_data.values():
        if isinstance(row_data, dict):
            for cell in row_data.values():
                if cell.get('v') not in (None, ''):
                    cells_with_values += 1

print(f"   Cells with values: {cells_with_values}")
print(f"   Empty cells: {total_cells - cells_with_values}")

# 7. Sample actual data
print("\n7. Sample data with values:")
sample_count = 0
for sheet_id, sheet in sheets.items():
    if sample_count >= 10:
        break
    cell_data = sheet.get('cellData', {})
    for row_key in sorted(cell_data.keys(), key=int)[:5]:
        if sample_count >= 10:
            break
        row_data = cell_data[row_key]
        if isinstance(row_data, dict):
            for col_key in sorted(row_data.keys(), key=int)[:5]:
                if sample_count >= 10:
                    break
                cell = row_data[col_key]
                if cell.get('v') not in (None, ''):
                    print(f"   [{row_key},{col_key}]: '{cell.get('v')}' (type: {cell.get('t')})")
                    sample_count += 1