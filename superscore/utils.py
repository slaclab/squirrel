import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SQUIRREL_SOURCE_PATH = Path(__file__).parent


def utcnow():
    return datetime.now(timezone.utc)


def build_abs_path(basedir: str, path: str) -> str:
    """
    Builds an abs path starting at basedir if path is not already absolute.
    ~ and ~user constructions will be expanded, so ~/path is considered absolute.
    If path is absolute already, this function returns path without modification.
    Parameters
    ----------
    basedir : str
        If path is not absolute already, build an abspath
        with path starting here.
    path : str
        The path to convert to absolute.
    """
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not os.path.isabs(path):
        return os.path.abspath(os.path.join(basedir, path))
    return path


def parse_csv_to_dict(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse CSV file representing PV data into a form that can be bulk-imported by the backend. Each row represents
    a PV and its associated meta-data.
    """
    result = []
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cleaned_headers = [h.strip() for h in reader.fieldnames if h and h.strip()]

        group_columns = [col for col in cleaned_headers if col not in ['Setpoint', 'Readback', 'Description']]

        for row_num, row in enumerate(reader, start=2):
            setpoint = row.get('Setpoint', '').strip()
            readback = row.get('Readback', '').strip()
            if not (setpoint or readback):
                continue
            desc_value = row.get('Description', '').strip()

            row_dict = {
                'Setpoint': setpoint,
                'Readback': readback,
                'Description': desc_value,
                'groups': {}
            }

            for group_name in group_columns:
                cell_value = row.get(group_name, '').strip()
                if cell_value and cell_value.lower() not in ['nan', 'none']:
                    values = [val.strip() for val in cell_value.split(',') if val.strip()]
                    row_dict['groups'][group_name] = values
                else:
                    row_dict['groups'][group_name] = []

            result.append(row_dict)
    return result
