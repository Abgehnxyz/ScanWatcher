"""
@file    run.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Einstiegspunkt fuer PyInstaller und direkte Ausfuehrung.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == "__main__":
    main()
