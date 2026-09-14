"""Preserve compiled Plane assets and add a dedicated planner route + menu link."""
from pathlib import Path
import re

index = Path('/usr/share/nginx/html/index.html')
text = index.read_text()
# Keep the prerendered element tree intact: load the menu after Plane's entry module.
text = text.replace('<script defer src="/oniro-planning/navigation.js"></script>', '')
if 'import("/oniro-planning/navigation.js")' not in text:
    pattern = r'import\("(/assets/entry\.client-[^"\n]+\.js)"\);'
    text, count = re.subn(pattern, r'import("\1").then(() => import("/oniro-planning/navigation.js"));', text)
    if count != 1:
        raise SystemExit('Unexpected Plane bootstrap; review before installing')
index.write_text(text)
conf = Path('/etc/nginx/nginx.conf')
text = conf.read_text()
marker = '# ONIRO daily planning v1'
if marker not in text:
    anchor = '    location / {'
    if text.count(anchor) != 1:
        raise SystemExit('Unexpected nginx configuration; review before installing')
    addition = ('    ' + marker + '\n'
                '    location ~ ^/[^/]+/planning/?$ {\n'
                '      root /usr/share/nginx/html;\n'
                '      add_header Cache-Control "no-store";\n'
                '      add_header X-Frame-Options "DENY" always;\n'
                '      add_header X-Content-Type-Options "nosniff" always;\n'
                '      add_header X-XSS-Protection "1; mode=block" always;\n'
                '      try_files /oniro-planning/index.html =404;\n'
                '    }\n'
                '    location /oniro-planning/ {\n'
                '      root /usr/share/nginx/html;\n'
                '      add_header Cache-Control "no-cache";\n'
                '      add_header X-Frame-Options "DENY" always;\n'
                '      add_header X-Content-Type-Options "nosniff" always;\n'
                '    }\n')
    conf.write_text(text.replace(anchor, addition + anchor, 1))
