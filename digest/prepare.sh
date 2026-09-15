set -euo pipefail
umask 077
cd /home/plane/oniro-digest/source
python3 -m unittest -v test_digest
python3 bootstrap.py
python3 runner.py smtp-check
python3 runner.py preview
