from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import tempfile
import xlwt
import base64
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/convert-to-xls")
async def convert_to_xls(request_data: Dict[str, Any]):
    """
    Convert Excel workbook data to .xls format using xlwt (OnlyOffice ready)
    This endpoint is only used when user wants to preserve .xls format
    """
    try:
        workbook_data = request_data.get('workbook_data', {})
        
        # Create xlwt workbook
        workbook = xlwt.Workbook(encoding='utf-8')
        
        # Style for basic formatting
        default_style = xlwt.XFStyle()
        date_style = xlwt.XFStyle()
        date_style.num_format_str = 'YYYY-MM-DD'
        
        # Process sheets
        sheet_order = workbook_data.get('sheetOrder', [])
        sheets_data = workbook_data.get('sheets', {})
        
        for sheet_id in sheet_order:
            sheet_data = sheets_data.get(sheet_id, {})
            sheet_name = sheet_data.get('name', f'Sheet{sheet_id}')
            
            # xlwt has limitations on sheet names
            sheet_name = sheet_name[:31]  # Max 31 chars
            sheet = workbook.add_sheet(sheet_name)
            
            # Process cell data
            cell_data = sheet_data.get('cellData', {})
            for cell_key, cell_info in cell_data.items():
                try:
                    row, col = map(int, cell_key.split('_'))
                    value = cell_info.get('v')
                    
                    if value is not None:
                        # Determine style based on value type
                        style = default_style
                        if isinstance(value, (int, float)):
                            # Numeric value
                            sheet.write(row, col, value, style)
                        elif isinstance(value, str):
                            # Text value
                            # xlwt has a limit of 32767 characters per cell
                            if len(value) > 32767:
                                value = value[:32764] + '...'
                            sheet.write(row, col, value, style)
                        else:
                            # Convert to string
                            sheet.write(row, col, str(value), style)
                    
                except Exception as e:
                    logger.warning(f"Failed to write cell {cell_key}: {str(e)}")
                    continue
            
            # Process column widths (limited support in xlwt)
            column_data = sheet_data.get('columnData', {})
            for col_index, col_info in column_data.items():
                try:
                    col_idx = int(col_index)
                    width = col_info.get('w', 80)
                    # Convert from Excel units to xlwt units (approximate)
                    sheet.col(col_idx).width = int(width * 40)
                except:
                    continue
        
        # Save to bytes
        output = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        workbook.save(output.name)
        
        # Read and encode
        with open(output.name, 'rb') as f:
            xls_data = f.read()
        
        # Clean up
        import os
        os.unlink(output.name)
        
        # Return base64 encoded data
        return {
            'success': True,
            'data': base64.b64encode(xls_data).decode('utf-8'),
            'format': 'xls',
            'limitations': [
                'Some formatting may be lost',
                'Formulas are converted to values',
                'Charts and images are not preserved',
                'Maximum 65536 rows and 256 columns per sheet'
            ]
        }
        
    except Exception as e:
        logger.error(f"XLS conversion failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert to XLS format: {str(e)}"
        )

@router.post("/convert-from-xls")
async def convert_from_xls(file_data: Dict[str, Any]):
    """
    Convert .xls file to standard Excel format (OnlyOffice ready)
    Currently handled by Rails Roo gem
    """
    return {
        'message': 'XLS reading is handled by Rails Roo gem',
        'supported': False
    }