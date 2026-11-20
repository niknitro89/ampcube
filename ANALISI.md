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

### Cosa NON è ancora risolto: campo a 0x04

Il valore a 32 bit all'offset 0x04 vale 0x000173E4 (AMPCUBE), 0x0001AC24 (PM) e
0x00013E44 (CFW). Il CFW lo ha cambiato, quindi dipende dal contenuto. Ipotesi già escluse:

- CRC16 di qualsiasi polinomio e init sulle sezioni, sull'header (ogni sottointervallo,
  con il campo azzerato) e sul file intero o il payload (polinomi comuni, 8 init);
- CRC32 (vari polinomi), Adler32, Fletcher, somme e XOR a 8, 16 e 32 bit;
- somme o combinazioni dei CRC delle sezioni.

**Finché questo campo non è noto, un firmware modificato potrebbe essere rifiutato dal
bootloader.** Nel caso peggiore il bootloader lo accetta senza controllarlo e il
dispositivo resta in uno stato non avviabile. Il modo più diretto per risolverlo:
analizzare con REA (`rea`, analisi .NET/nativa) il Sonicake Manager o la `5868USB.dll`,
cioè lo strumento che genera e invia questi file.

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
