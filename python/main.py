#!/usr/bin/env python3

import sys
import glob
import serial
from serial.tools import list_ports
import pyautogui
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from time import sleep
import threading
import queue

pyautogui.PAUSE = 0  
pyautogui.FAILSAFE = False

# Cria a fila para a comunicação entre a Thread de leitura e a interface
fila_mouse = queue.Queue()

BUTTON_MAP = {
    3: "R",
    4: "Y",
    5: "B",
    6: "G",
}

def move_mouse(axis, value):
    """Move o mouse ou clica de acordo com o eixo e valor recebidos."""
    if axis == 0:
        pyautogui.moveRel(value, 0)
    elif axis == 1:
        pyautogui.moveRel(0, value)
    elif axis == 2: # Lógica do clique adicionada!
        if value == 1:
            pyautogui.mouseDown()
        elif value == 0:
            pyautogui.mouseUp()

def controle(ser):
    """
    Loop que lê bytes da porta serial em segundo plano.
    """
    while ser.is_open:
        try:
            sync_byte = ser.read(size=1)
            if not sync_byte:
                continue
            if sync_byte[0] == 0xFF:
                data = ser.read(size=3)
                if len(data) < 3:
                    continue
                # print(data) # Comentei o print para não floodar o terminal, mas pode descomentar para debugar
                axis, value = parse_data(data)
                if axis in BUTTON_MAP:
                    estado = "pressionado" if value == 1 else "solto"
                    print(f"Botao {BUTTON_MAP[axis]}: {estado}")
                else:
                    print(f"Recebido -> Eixo: {axis} | Valor: {value}")
                    # Coloca na fila em vez de mover direto
                    fila_mouse.put((axis, value))
                
        except serial.SerialException:
            break
        except Exception as e:
            print(f"Erro na leitura: {e}")
            break

def processar_fila_mouse(root):
    """A janela principal roda isso para esvaziar a fila e mover o mouse de forma segura."""
    try:
        while True:
            axis, value = fila_mouse.get_nowait()
            move_mouse(axis, value)
    except queue.Empty:
        pass 
    
    # Repete a verificação a cada 10ms
    root.after(10, lambda: processar_fila_mouse(root))

def serial_ports():
    if sys.platform.startswith('win'):
        return [port.device for port in list_ports.comports()]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        return glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        return glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Plataforma não suportada para detecção de portas seriais.')

def parse_data(data):
    axis = data[0]
    value = int.from_bytes(data[1:3], byteorder='little', signed=True)
    return axis, value

def conectar_porta(port_name, root, botao_conectar, status_label, mudar_cor_circulo):
    if not port_name:
        return

    # Inicia a variável como None para evitar o erro do "finally"
    ser = None 

    try:
        ser = serial.Serial(port_name, 115200, timeout=1)
        status_label.config(text=f"Conectado em {port_name}", foreground="green")
        mudar_cor_circulo("green")
        if botao_conectar is not None:
            botao_conectar.config(text="Conectado", state="disabled")
        root.update()

        # Inicia a Thread de leitura
        leitura_thread = threading.Thread(target=controle, args=(ser,), daemon=True)
        leitura_thread.start()

    except Exception as e:
        messagebox.showerror("Erro de Conexão", f"Não foi possível conectar em {port_name}.\nErro: {e}")
        mudar_cor_circulo("red")
        if ser and ser.is_open:
            ser.close()

def criar_janela():
    root = tk.Tk()
    root.title("Controle de Mouse")
    root.geometry("800x250")
    root.resizable(False, False)

    dark_bg = "#2e2e2e"
    dark_fg = "#ffffff"
    accent_color = "#007acc"
    root.configure(bg=dark_bg)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=dark_bg)
    style.configure("TLabel", background=dark_bg, foreground=dark_fg, font=("Segoe UI", 11))
    style.configure("TButton", font=("Segoe UI", 10, "bold"), foreground=dark_fg, background="#444444", borderwidth=0)
    style.map("TButton", background=[("active", "#555555")])
    style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"), foreground=dark_fg, background=accent_color, padding=6)
    style.map("Accent.TButton", background=[("active", "#005f9e")])

    style.configure("TCombobox", fieldbackground=dark_bg, background=dark_bg, foreground=dark_fg, padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", dark_bg)])

    frame_principal = ttk.Frame(root, padding="20")
    frame_principal.pack(expand=True, fill="both")

    titulo_label = ttk.Label(frame_principal, text="Controle de Mouse", font=("Segoe UI", 14, "bold"))
    titulo_label.pack(pady=(0, 10))

    porta_var = tk.StringVar(value="")
    portas_disponiveis = []

    def atualizar_portas():
        nonlocal portas_disponiveis
        portas_disponiveis = serial_ports()
        port_dropdown["values"] = portas_disponiveis

        if portas_disponiveis:
            porta_var.set(portas_disponiveis[0])
            status_label.config(text="Porta serial detectada. Selecione a COM do Bluetooth.", foreground="white")
        else:
            porta_var.set("")
            status_label.config(text="Nenhuma porta serial detectada. Verifique pareamento Bluetooth/driver.", foreground="orange")

    footer_frame = tk.Frame(root, bg=dark_bg)
    footer_frame.pack(side="bottom", fill="x", padx=10, pady=(10, 0))

    status_label = tk.Label(footer_frame, text="Aguardando seleção de porta...", font=("Segoe UI", 11), bg=dark_bg, fg=dark_fg)
    status_label.grid(row=0, column=0, sticky="w")

    port_dropdown = ttk.Combobox(footer_frame, textvariable=porta_var, values=portas_disponiveis, state="readonly", width=12)
    port_dropdown.grid(row=0, column=1, padx=10)
    port_dropdown.bind(
        "<<ComboboxSelected>>",
        lambda event: conectar_porta(porta_var.get(), root, None, status_label, mudar_cor_circulo)
    )

    atualizar_portas()

    botao_atualizar = ttk.Button(
        footer_frame,
        text="Atualizar",
        command=atualizar_portas
    )
    botao_atualizar.grid(row=0, column=2, padx=(0, 10))

    circle_canvas = tk.Canvas(footer_frame, width=20, height=20, highlightthickness=0, bg=dark_bg)
    circle_item = circle_canvas.create_oval(2, 2, 18, 18, fill="red", outline="")
    circle_canvas.grid(row=0, column=3, sticky="e")

    footer_frame.columnconfigure(1, weight=1)

    def mudar_cor_circulo(cor):
        circle_canvas.itemconfig(circle_item, fill=cor)

    def conectar_porta_automatica():
        if porta_var.get():
            conectar_porta(porta_var.get(), root, None, status_label, mudar_cor_circulo)

    # Dá a partida no loop que lê a fila de forma segura
    processar_fila_mouse(root)

    root.after(100, conectar_porta_automatica)

    root.mainloop()

if __name__ == "__main__":
    criar_janela()