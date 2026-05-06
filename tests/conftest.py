"""Конфигурация pytest."""

import sys
from pathlib import Path

# Делаем доступными модули из etl/ и monitoring/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
sys.path.insert(0, str(ROOT / "monitoring"))
