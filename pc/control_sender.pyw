# Control del sender de Elite: INICIAR / PARAR con el raton (doble clic, sin consola)
import os, sys, subprocess, threading, time, tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "elite_sender.log")
NOWIN = 0x08000000  # CREATE_NO_WINDOW
PAT = "*elite_sender.*"   # coincide con elite_sender.bat y elite_sender.py

def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                          text=True, creationflags=NOWIN).stdout

def corriendo():
    out = ps("(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '%s' "
             "-and $_.CommandLine -notlike '*control_sender*' -and $_.ProcessId -ne $PID }).Count" % PAT)
    try:
        return int(out.strip() or 0) > 0
    except ValueError:
        return False

def parar():
    ps("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '%s' "
       "-and $_.CommandLine -notlike '*control_sender*' -and $_.ProcessId -ne $PID } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % PAT)

def iniciar():
    parar()
    subprocess.Popen(["cmd", "/c", os.path.join(DIR, "elite_sender.bat")], cwd=DIR, creationflags=NOWIN)

def acceso_directo():
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    lnk = os.path.join(os.path.expanduser("~"), "Desktop", "Elite Sender.lnk")
    ps("$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\Elite Sender.lnk');"
       f"$s.TargetPath='{exe}';$s.Arguments='\"{os.path.abspath(__file__)}\"';$s.WorkingDirectory='{DIR}';"
       "$s.IconLocation='shell32.dll,137';$s.Save()")
    return lnk

# ---------- ventana ----------
NEG, NAR, VER, ROJ, GRI = "#000000", "#ff8c00", "#3ad13a", "#e03030", "#666666"
root = tk.Tk()
root.title("Elite Sender")
root.configure(bg=NEG)
root.geometry("460x330")
root.resizable(False, False)

estado = tk.Label(root, text="COMPROBANDO...", font=("Segoe UI", 18, "bold"), bg=NEG, fg=GRI)
estado.pack(pady=(14, 8))

fila = tk.Frame(root, bg=NEG); fila.pack()
def boton(txt, col, fn):
    b = tk.Button(fila, text=txt, font=("Segoe UI", 14, "bold"), width=10, bg=NEG, fg=col,
                  activebackground=col, activeforeground=NEG, relief="solid", bd=2,
                  highlightbackground=col, command=lambda: accion(fn))
    b.pack(side="left", padx=10); return b
b_ini = boton("INICIAR", VER, iniciar)
b_par = boton("PARAR", ROJ, parar)

log = tk.Text(root, height=8, width=56, bg="#111111", fg=NAR, font=("Consolas", 9), bd=0, wrap="none")
log.pack(padx=10, pady=12)

pie = tk.Frame(root, bg=NEG); pie.pack(fill="x", padx=10)
aviso = tk.Label(pie, text="", font=("Segoe UI", 8), bg=NEG, fg=GRI); aviso.pack(side="left")
tk.Button(pie, text="Acceso en escritorio", font=("Segoe UI", 8), bg=NEG, fg=GRI, relief="flat",
          command=lambda: aviso.config(text="Creado: " + os.path.basename(acceso_directo()))).pack(side="right")

def accion(fn):
    estado.config(text="...", fg=GRI)
    threading.Thread(target=lambda: (fn(), time.sleep(1.5), comprobar()), daemon=True).start()

def comprobar():
    on = corriendo()
    root.after(0, lambda: estado.config(text="● ENVIANDO" if on else "○ PARADO", fg=VER if on else ROJ))

def bucle():
    while True:
        comprobar(); time.sleep(3)

def leer_log():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            txt = "".join(f.readlines()[-8:])
    except OSError:
        txt = "(sin log todavía)"
    log.delete("1.0", "end"); log.insert("end", txt)
    root.after(2000, leer_log)

threading.Thread(target=bucle, daemon=True).start()
leer_log()
root.mainloop()
