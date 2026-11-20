#!/usr/bin/env python3
"""Genera tools/ampcube_editor.html: un unico file con catalogo effetti, icone e font incorporati."""
import base64, json, os
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'editor.src.html'), encoding='utf8').read()
cat = json.load(open(os.path.join(here, '..', 'tools', 'data', 'ampcube_v123_catalog.json')))
icons = {}
for f in os.listdir(os.path.join(here, 'assets', 'icons')):
    svg = open(os.path.join(here, 'assets', 'icons', f), encoding='utf8').read()
    icons[f[:-4]] = svg.replace('currentColor', 'currentColor').strip()
font = base64.b64encode(open(os.path.join(here, 'assets', 'Oswald.ttf'), 'rb').read()).decode()
out = (src.replace('/*CATALOG*/null', json.dumps(cat, separators=(',', ':')))
          .replace('/*ICONS*/null', json.dumps(icons))
          .replace('/*FONT*/', font))
dst = os.path.join(here, '..', 'tools', 'ampcube_editor.html')
open(dst, 'w', encoding='utf8').write(out)
print('scritto', dst, len(out), 'byte')
