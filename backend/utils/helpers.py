import os
import uuid
from typing import Dict, Any
from datetime import datetime

def generate_report_id() -> str:
    """Genererar unikt rapport-ID"""
    return str(uuid.uuid4())

def format_currency(amount: float) -> str:
    """Formaterar belopp med tusentalsavgränsare"""
    return f"{amount:,.0f}".replace(",", " ")

def validate_se_file(file_path: str) -> bool:
    """Validerar att filen är en giltig .SE-fil"""
    if not os.path.exists(file_path):
        return False
    
    if not file_path.endswith('.se'):
        return False
    
    # Kontrollera att filen innehåller grundläggande .SE-struktur
    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read(1000)  # Läs första 1000 tecken
            if '#ORG' in content or '#UB' in content:
                return True
    except:
        pass
    
    return False

def create_temp_directory() -> str:
    """Skapar temporär mapp för filhantering"""
    temp_dir = f"temp/{generate_report_id()}"
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def cleanup_temp_files(temp_path: str):
    """Rensar upp temporära filer"""
    try:
        if os.path.exists(temp_path):
            if os.path.isdir(temp_path):
                import shutil
                shutil.rmtree(temp_path)
            else:
                os.remove(temp_path)
    except Exception as e:
        print(f"Varning: Kunde inte rensa temporära filer: {e}")

def get_file_size_mb(file_path: str) -> float:
    """Hämtar filstorlek i MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except:
        return 0.0

def sanitize_filename(filename: str) -> str:
    """Saniterar filnamn för säker lagring"""
    import re
    # Ta bort eller ersätt farliga tecken
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Begränsa längd
    if len(sanitized) > 100:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:95] + ext
    return sanitized 