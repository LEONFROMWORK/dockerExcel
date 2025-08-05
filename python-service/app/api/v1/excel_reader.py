from fastapi import APIRouter, UploadFile, File
from typing import Dict, Any
import pandas as pd
import numpy as np
import logging
from io import BytesIO
import traceback

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/read")
async def read_excel_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Read Excel file and return its data in JSON format
    """
    try:
        # Read file content
        content = await file.read()
        file_buffer = BytesIO(content)

        # Read all sheets
        excel_file = pd.ExcelFile(file_buffer)
        sheets_data = {}
        sheets_info = []

        for sheet_name in excel_file.sheet_names:
            # Read sheet data
            df = pd.read_excel(file_buffer, sheet_name=sheet_name)

            # Convert DataFrame to list of dictionaries
            # Replace NaN with None for JSON serialization
            df = df.where(pd.notnull(df), None)

            # Replace inf and -inf with None
            df = df.replace([float("inf"), float("-inf")], None)

            # Get column types
            column_types = {}
            for col in df.columns:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    col_type = "number"
                elif "float" in dtype:
                    col_type = "number"
                elif "datetime" in dtype:
                    col_type = "date"
                elif "bool" in dtype:
                    col_type = "boolean"
                else:
                    col_type = "text"
                column_types[col] = col_type

            # Convert to dict with proper handling of special float values
            rows_data = []
            for _, row in df.iterrows():
                row_dict = {}
                for col in df.columns:
                    value = row[col]
                    # Handle special float values
                    if pd.isna(value) or (
                        isinstance(value, float)
                        and (np.isinf(value) or np.isnan(value))
                    ):
                        row_dict[col] = None
                    else:
                        row_dict[col] = value
                rows_data.append(row_dict)

            sheets_data[sheet_name] = {
                "rows": rows_data,
                "columns": [
                    str(col) for col in df.columns
                ],  # Ensure column names are strings
                "column_types": column_types,
                "row_count": len(df),
                "column_count": len(df.columns),
            }

            sheets_info.append(
                {"name": sheet_name, "rows": len(df), "columns": len(df.columns)}
            )

        # Get file metadata
        metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "sheet_count": len(excel_file.sheet_names),
            "sheets": sheets_info,
        }

        return {
            "success": True,
            "data": sheets_data,
            "sheets": excel_file.sheet_names,
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"Failed to read Excel file: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "data": {},
            "sheets": [],
            "metadata": {},
        }
