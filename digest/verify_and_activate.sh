set -euo pipefail
cd /home/plane/oniro-digest/source
python3 -m unittest -v test_digest
python3 runner.py test-manager
python3 activate.py
python3 runner.py status
crontab -l
