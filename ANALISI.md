# AMPCUBE firmware – analisi e toolkit

Analisi basata su tre file:

| File | Modello | Versione | Compressione |
|---|---|---|---|
| `AMPCUBE_Firmware_V1.2.3.bin` | AMPCUBE | V1.2.3 | LZO1X-1 |
| `Pocket_Master_Firmware_V1.3.3.bin` | Pocket Master | V1.3.3 | nessuna |
| `PocketMaster_CFW1.0.2_base1.3.31.bin` | Pocket Master (CFW) | V1.3.3 | nessuna |

## Formato HTFW (risolto)

Il formato è documentato in testa a `htfw.py`. In sintesi:

- header di 0x88 byte con una tabella di 5 sezioni (`c`, `g`, `f`, `b`, `e`);
- **CRC per sezione = CRC16/MODBUS** (poly 0x8005 riflesso, init 0xFFFF), salvato big-endian.
  È verificato su tutte le 15 sezioni dei 3 file;
- l'AMPCUBE ha il flag di compressione a 1. Il payload è `u32 dimensione` seguito da uno
  stream **LZO1X**. Ricomprimendo con `lzo1x_1` si ottiene il file originale identico byte per byte.

`htfw.py unpack` seguito da `htfw.py repack` rigenera i file originali identici, sia per
l'AMPCUBE sia per il Pocket Master.

### Checksum dell'header (risolto con la DLL)

La funzione `checkCrc` di `5868USB.dll` (Sonicake Manager) calcola il CRC16/MODBUS
con tabelle hi/lo e init 0xFF/0xFF su `file[6 : dimensione_file]` e lo confronta con la
word all'offset 0x04, salvata big-endian. Il calcolo torna su tutti e tre i file.
I byte 6-7 (0x0001) fanno parte dei dati coperti dal CRC.

`isRealFirmware` (funzione a RVA 0xE0860) controlla anche:

- che il magic sia `HTFW`;
- che il nome del modello all'offset 0x0C sia quello del dispositivo collegato;
- che la dimensione all'offset 0x08 sia uguale alla dimensione reale del file.

`htfw.py repack` ricalcola tutti questi campi.

## Architettura

- `c` @0x200000 e `g` @0x240000: codice ARM Thumb (Cortex-M, Keil). Nel PM il CFW
  aggiunge qui le sue tabelle di hook (`CFWG`, `CFWH`, `FX2L free`).
- `b` @0x000000: codice Andes NDS32 (istruzioni big-endian `48 xx xx xx` = `j`). È il blocco più grande.
- `f` @0x280000: configurazione.
- `e` @0x190000: preset e dati utente (record `A5 5A ...`).

## Il CFW del Pocket Master

Il CFW 1.0.2 non è una patch di pochi byte. Ingrandisce tutte le sezioni (`b` di circa
+50 KB, `c` di circa +10 KB, `f` di +4 KB) e aggiunge:

- menu UI Style con i temi Default, Amber CRT, Tube Amp, Synthwave, Stage Hi-Contrast e
  Game Boy, più la luminosità;
- menu I/O, MIDI (canale, CC1 AGAIN, TAP DIV), G-EQ e USB REC (WET / DRY DI / DI|WET);
- nuovi modelli di ampli ed effetti (Calif IIC+, Brit 900, Dizzy VH+, BBD Phaser, Duck Verb, ...);
- il supporto ai profili "Refine 512" (FIR da 512 tap, vedi l'SDK NAM).

Questi hook puntano a indirizzi precisi della build 1.3.3x del PM. **Non si possono copiare
sull'AMPCUBE.** È un altro prodotto, con un'altra build (V1.2.3) e un altro hardware:
non ha display, quindi i temi e i menu grafici non hanno senso. Ogni funzione andrebbe
re-implementata a mano nel codice ARM/NDS32 dell'AMPCUBE.

## Uso

```bash
python3 htfw.py info AMPCUBE_Firmware_V1.2.3.bin
python3 htfw.py unpack AMPCUBE_Firmware_V1.2.3.bin ac_unpacked
# ... modifica ac_unpacked/sec_*.bin ...
python3 htfw.py repack ac_unpacked AMPCUBE_mod.bin
```

Requisito: `liblzo2` (`apt install liblzo2-2`).

## Informazioni dal sito del CFW (pocketmaster-cfw.guitar-training-generator.com)

- **10 clone (.clo/NAM) e 10 User IR** invece di 5. Al primo avvio del CFW gli slot vengono
  riformattati con un nuovo layout in flash, e IR e clone presenti vanno persi. Gli slot 6-10 e
  i nomi da 30 caratteri si gestiscono solo con la web app del CFW (un fork di SonicMaster),
  non con Sonicake Manager.
- **Riverberi:** "five extra reverbs" più knob extra e Trails su quelli di serie, con un "DSP più
  leggero". Gli ID degli algoritmi nuovi vanno da 0xC0 a 0xC4 e sono codice DSP nuovo.
- **Bootloader:** non è incluso nel file di aggiornamento. Se un aggiornamento fallisce, il
  Pocket Master si avvia in modalità update tenendo premuti FS1 + FS2 + VOL/VALUE
  all'accensione. La combinazione per l'AMPCUBE non è nota.
- **Backup completo:** dump della SPI flash con un programmatore CH341A e una clip SOP-8.
- **Progetti collegati:** Smart Box CFW e Amphonix 2 CFW (stesso autore),
  github.com/egorcipa8-debug/gp150-htfw, github.com/klotznick/pocket-master-interoperability-guide,
  github.com/Skyggedans/SonicMaster, github.com/MigueLesPaul/sonicake-pocket-master-linux-flash.

## Protocollo editor AMPCUBE (verificato con dump reali, 20/11/2026)

Lo stesso SysEx del Pocket Master: nibble encoding, CRC-8 poly 0x07, frammenti da 19 byte.

- `12 41` stato live / `12 4F` preset salvato: TLV `[sec u16][len u16]{[fid u16][len u16][val]}`.
  L'AMPCUBE ha **9 moduli** (il Pocket Master 10), con 8 parametri float32 per modulo.
  Sezione 0002: 3001 = maschera on/off, 3002 = catena, 3003 = ID effetto (`cat<<24 | idx`),
  3004 = 72 float.
- Moduli AMPCUBE: 0 PRE (gate/comp/wah/boost), 1 DRV, 2 AMP, 3 CAB, 4 EQ, 5 MOD, 6 DLY,
  7 RVB, 8 CLONE (cat 0x0F).
- Scritture: `11 43 u32` seleziona il preset, `11 47 u32 mod u32 mod u32 effetto`,
  `11 48 u32 mod u32 param f32 valore`, `11 49 u32 mod u32 on`, `11 42 01 20 01 00 vol`,
  `11 4A u32 slot nome[10] 00 00 00` salva il preset.
- Il catalogo effetti estratto dal firmware è in `tools/data/ampcube_v123_catalog.json`:
  tabella in `e`+0x10000 (offset per modulo, poi record di effetti) e cab in `f`.
- L'editor è `tools/ampcube_editor.html`, generato da `web/build.py`.
