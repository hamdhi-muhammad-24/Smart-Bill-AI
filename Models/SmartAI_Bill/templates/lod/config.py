import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CLIENTS_XLSX = os.path.join(DATA_DIR, 'LOD LIST 90 (23.03.2026) 22569.xlsx')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
TRANSLATION_PAGE = os.path.join(BASE_DIR, 'assets', 'translation_page.pdf')