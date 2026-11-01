#!/bin/bash
# Panel Elite en la Pi 3 de KORZO (Raspberry Pi OS Lite, equipo "elite", usuario "elite")
# Uso:  bash instalar_pi3.sh
set -e
[ -f ~/panel.py ] || { echo "Falta /home/elite/panel.py"; exit 1; }
echo "== Paquetes"
sudo apt update && sudo apt install -y python3-pygame python3-numpy python3-evdev espeak-ng
echo "== Servicio del panel"
sudo tee /etc/systemd/system/elite-panel.service >/dev/null <<'EOS'
[Unit]
Description=Elite Panel
After=network-online.target
[Service]
ExecStartPre=/bin/sh -c 'echo 0 > /sys/class/graphics/fbcon/cursor_blink; dmesg -n 1'
ExecStart=/usr/bin/python3 /home/elite/panel.py
Restart=always
[Install]
WantedBy=multi-user.target
EOS
echo "== Sin escritorio (la HDMI es para el panel)"
sudo systemctl set-default multi-user.target
[ -s ~/notas.json ] || echo "[]" > ~/notas.json
sudo chown -R elite:elite /home/elite
sudo systemctl daemon-reload
sudo systemctl enable elite-panel
echo
echo "LISTO. Reinicia:  sudo reboot"
