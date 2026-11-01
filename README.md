# Panel Elite Dangerous (Raspberry Pi)

Panel táctil y tablero HDMI para Elite Dangerous. Creado por CMDR ORTEM ED DER y Claude. Versión actual: **v0.86**.

- `pi4_ortem/panel.py` – panel de Ortem (Pi 4)
- `pi3_korzo/` – panel de KORZO (Pi 3) e instalador
- `pc/` – sender del PC de juego y su configuración
- `parches/` – parches versión a versión
- `HISTORIAL.txt` – todo lo hecho y decidido · `LEEME.txt` – instalación

## Actualizar la Pi de Ortem
```
cd ~/panel-elite && git pull && cp pi4_ortem/panel.py ~/ && sudo systemctl restart elite-panel
```
La clave de Inara (`inara_clave.txt`) no se sube nunca: está en `.gitignore`.
