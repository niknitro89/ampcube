#!/usr/bin/env python3
"""Genera tools/ampcube_editor.html inserendo il catalogo effetti estratto dal firmware."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'editor.src.html'), encoding='utf8').read()
cat = json.load(open(os.path.join(here, '..', 'tools', 'data', 'ampcube_v123_catalog.json')))
out = src.replace('/*CATALOG*/null', json.dumps(cat, separators=(',', ':')))
dst = os.path.join(here, '..', 'tools', 'ampcube_editor.html')
open(dst, 'w', encoding='utf8').write(out)
print('scritto', dst, len(out), 'byte')
