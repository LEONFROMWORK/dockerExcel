#!/usr/bin/env python3
"""
Check actual values in the output
"""
import json

with open('test_color_fix_output.json', 'r') as f:
    data = json.load(f)
    sheet = data['sheets']['sheet-0']
    
    # Check sample cells with actual values
    print('Sample cells with values:')
    count = 0
    for row_key, row_data in sheet['cellData'].items():
        for col_key, cell in row_data.items():
            if cell.get('v') and cell['v'] != '' and count < 10:
                print(f'  [{row_key},{col_key}]: {cell["v"]}')
                count += 1