"""
Legacy smoke script kept for convenience. The real isolation test-suite lives in
tests/test_tenant_isolation.py  ->  run with:  python -m pytest tests -q
"""
import subprocess
import sys

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests", "-q"]))
