"""Preserve compiled Plane assets and add a dedicated planner route + menu link."""
from pathlib import Path

index = Path('/usr/share/nginx/html/index.html')
text = index.read_text()
script = '<script defer src="/oniro-planning/navigation.js"></script>'
if script not in text:
    if '</head>' not in text:
        raise SystemExit('Unexpected Plane index structure')
    index.write_text(text.replace('</head>', script + '</head>', 1))
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
