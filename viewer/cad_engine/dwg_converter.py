import os
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)

DWG_VERSION_MAP = {
    b'AC1032': 'AutoCAD 2018 / 2021 / 2024',
    b'AC1027': 'AutoCAD 2013 / 2014 / 2015 / 2016 / 2017',
    b'AC1024': 'AutoCAD 2010 / 2011 / 2012',
    b'AC1021': 'AutoCAD 2007 / 2008 / 2009',
    b'AC1018': 'AutoCAD 2004 / 2005 / 2006',
    b'AC1015': 'AutoCAD 2000 / 2000i / 2002',
    b'AC1014': 'AutoCAD Release 14',
    b'AC1012': 'AutoCAD Release 13',
}

class DwgConversionError(Exception):
    def __init__(self, message, version_str=None, suggestions=None):
        super().__init__(message)
        self.version_str = version_str or "Unknown DWG version"
        self.suggestions = suggestions or []

def detect_dwg_version(file_path):
    """Reads the binary header of a DWG file to detect AutoCAD version."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(6)
            for magic, ver in DWG_VERSION_MAP.items():
                if header.startswith(magic):
                    return ver
            return f"DWG header {header.decode('latin1', errors='ignore')}"
    except Exception as e:
        logger.warning(f"Failed to read DWG header: {e}")
        return "Unknown DWG format"

def is_dwg_converter_available():
    """Checks if a known CAD converter CLI is available in PATH."""
    return shutil.which('dwg2dxf') is not None or shutil.which('ODAFileConverter') is not None

def convert_dwg_to_dxf(dwg_path, output_dir=None):
    """
    Attempts to convert DWG to DXF using LibreDWG (dwg2dxf) or ODAFileConverter.
    If unavailable, raises DwgConversionError with clear guidance.
    """
    version_info = detect_dwg_version(dwg_path)
    base_name = os.path.splitext(os.path.basename(dwg_path))[0]
    out_dir = output_dir or os.path.dirname(dwg_path)
    dxf_path = os.path.join(out_dir, f"{base_name}_converted.dxf")

    dwg2dxf_bin = shutil.which('dwg2dxf')
    if dwg2dxf_bin:
        try:
            # dwg2dxf input.dwg -o output.dxf
            res = subprocess.run([dwg2dxf_bin, dwg_path, '-o', dxf_path, '-y'], capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and os.path.exists(dxf_path) and os.path.getsize(dxf_path) > 0:
                logger.info(f"Successfully converted {dwg_path} to {dxf_path}")
                return dxf_path
            else:
                logger.warning(f"dwg2dxf returned non-zero ({res.returncode}): {res.stderr}")
        except Exception as ex:
            logger.error(f"Error executing dwg2dxf: {ex}")

    # No converter available or conversion failed
    suggestions = [
        "In AutoCAD or Revit: Use 'Save As' or 'Export' and select AutoCAD DXF format (R2018 or R2013).",
        "Export the sheet as a Vector PDF directly from AutoCAD/Revit for instant multi-layer viewing.",
        "Install the open-source LibreDWG tool (`brew install libredwg`) on the host system to enable automatic DWG-to-DXF server conversion.",
        "Use free Autodesk DWG TrueView to convert proprietary DWG files to standard ASCII DXF."
    ]

    raise DwgConversionError(
        message=(
            f"DWG format ({version_info}) is Autodesk's proprietary binary CAD specification. "
            f"Direct binary decoding requires server-side LibreDWG (`dwg2dxf`) or ODA converter, which is not currently installed."
        ),
        version_str=version_info,
        suggestions=suggestions
    )
