#!/bin/bash

# ==============================================================================
# DRAGON FLY SYSTEM - AUTO INSTALLER (DESKTOP EDITION)
# ==============================================================================

# Colores
RED='\033[0;31m'
DARK_GRAY='\033[1;30m'
WHITE='\033[1;37m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Detectar usuario real (incluso si se ejecuta con sudo)
TARGET_USER=${SUDO_USER:-$(whoami)}
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
PROJECT_DIR=$(pwd)

# Función para centrar texto de una sola línea en la terminal
print_center() {
    local text="$1"
    local color="$2"
    local term_width=$(tput cols 2>/dev/null || echo 80)
    local padding="$(printf '%0.1s' ' '{1..500})"
    local text_len=${#text}
    local pad_len=$(( (term_width - text_len) / 2 ))
    [[ $pad_len -lt 0 ]] && pad_len=0
    printf "${color}%*.*s%s${NC}\n" 0 "$pad_len" "$padding" "$text"
}

# Banner con Arte ASCII centrado dinámicamente
draw_banner() {
    clear
    local term_width=$(tput cols 2>/dev/null || echo 80)
    
    local max_len=61 
    local pad_len=$(( (term_width - max_len) / 2 ))
    [[ $pad_len -lt 0 ]] && pad_len=0
    
    local padding=$(printf '%*s' "$pad_len" "")

    echo -e "${RED}"
    while IFS= read -r line; do
        echo "${padding}${line}"
    done << 'EOF'


     ·▄▄▄▄  ▄▄▄   ▄▄▄·  ▄▄ •        ▐ ▄ ·▄▄▄▄▄▌   ▄· ▄▌
     ██▪ ██ ▀▄ █·▐█ ▀█ ▐█ ▀ ▪▪      •█▌▐█▐▄▄·██•  ▐█▪██▌
     ▐█· ▐█▌▐▀▀▄ ▄█▀▀█ ▄█ ▀█▄ ▄█▀▄ ▐█▐▐▌██▪ ██▪  ▐█▌▐█▪
     ██. ██ ▐█•█▌▐█ ▪▐▌▐█▄▪▐█▐█▌.▐▌██▐█▌██▌.▐█▌▐▌ ▐█▀·.
     ▀▀▀▀▀• .▀  ▀ ▀  ▀ ·▀▀▀▀  ▀█▄▀▪▀▀ █▪▀▀▀ .▀▀▀   ▀ • 

EOF
    echo -e "${NC}"
    
    print_center "=== INSTALADOR DESKTOP - RED TEAM TOOLBOX ===" "${WHITE}"
    print_center "Preparando entorno gráfico para auditorías" "${DARK_GRAY}"
    echo ""
}

# 1. Instalar Dependencias
instalar_dependencias() {
    print_center "[*] Actualizando repositorios e instalando dependencias base..." "${RED}"
    apt-get update -y
    
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3 python3-tk python3-serial git \
        nmap macchanger aircrack-ng hostapd dnsmasq iptables \
        network-manager bluez rfkill lxterminal python3-pil python3-pil.imagetk \
        python3-netifaces python3-aioquic

    # Instalación de CustomTkinter global (Para evitar errores con Sudo)
    print_center "[*] Asegurando entorno de interfaz gráfica..." "${DARK_GRAY}"
    pip3 install customtkinter --break-system-packages 2>/dev/null

    print_center "[+] Dependencias instaladas correctamente." "${GREEN}"
    sleep 2
}

# 2. Configurar Auto-Inicio y Permisos (Sudoers)
configurar_sistema() {
    # Configuración de inicio automático de sesión
    if [ -f /etc/lightdm/lightdm.conf ]; then
        print_center "[*] Configurando gestor de arranque gráfico..." "${RED}"
        sudo sed -i "s/^#autologin-user=.*/autologin-user=$TARGET_USER/" /etc/lightdm/lightdm.conf
        sudo sed -i 's/^#autologin-user-timeout=0/autologin-user-timeout=0/' /etc/lightdm/lightdm.conf
    fi

    print_center "[*] Configurando auto-inicio del sistema Dragon-Fly..." "${RED}"
    mkdir -p "$TARGET_HOME/.config/autostart"
    
    cat << EOF > "$TARGET_HOME/.config/autostart/dragonfly_desktop.desktop"
[Desktop Entry]
Type=Application
Name=DragonFly Desktop
Comment=Sistema Red Team
Exec=sudo /usr/bin/python3 $PROJECT_DIR/desktop.py
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
    
    chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/autostart"

    print_center "[*] Otorgando permisos de ejecución NOPASSWD en sudoers..." "${RED}"
    echo "$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/python3 $PROJECT_DIR/desktop.py" | sudo tee /etc/sudoers.d/010_dragonfly > /dev/null
    chmod 0440 /etc/sudoers.d/010_dragonfly

    print_center "[+] Sistema y auto-arranque configurados correctamente." "${GREEN}"
    sleep 2
}

# 3. Instalar y configurar Responder
instalar_responder() {
    print_center "[*] Clonando Responder en /opt/..." "${RED}"
    
    if [ -d "/opt/Responder" ]; then
        print_center "[!] Eliminando instalación previa de Responder..." "${DARK_GRAY}"
        rm -rf /opt/Responder
    fi

    git clone https://github.com/lgandx/Responder.git /opt/Responder
    chmod -R 755 /opt/Responder

    print_center "[*] Generando certificados SSL..." "${RED}"
    mkdir -p /opt/Responder/certs
    
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout /opt/Responder/certs/responder.key \
        -out /opt/Responder/certs/responder.crt \
        -days 3650 -subj "/CN=DragonFly" 2>/dev/null

    chmod 644 /opt/Responder/certs/responder.crt
    chmod 600 /opt/Responder/certs/responder.key

    print_center "[+] Responder instalado y configurado correctamente." "${GREEN}"
    sleep 2
}

# 4. Desinstalar Todo
desinstalar_todo() {
    print_center "!!! ADVERTENCIA !!!" "${RED}"
    print_center "Esto eliminará Auto-inicio y Responder." "${WHITE}"
    
    local term_width=$(tput cols 2>/dev/null || echo 80)
    local menu_width=50
    local pad_len=$(( (term_width - menu_width) / 2 ))
    [[ $pad_len -lt 0 ]] && pad_len=0
    local padding=$(printf '%*s' "$pad_len" "")

    read -p "${padding}¿Estás seguro de continuar? (s/n): " confirmar
    
    if [[ "$confirmar" =~ ^[Ss]$ ]]; then
        if [ -f /etc/lightdm/lightdm.conf ]; then
            print_center "[*] Revirtiendo configuración de inicio..." "${DARK_GRAY}"
            sed -i "s/^autologin-user=$TARGET_USER/#autologin-user=/" /etc/lightdm/lightdm.conf
            sed -i 's/^autologin-user-timeout=0/#autologin-user-timeout=0/' /etc/lightdm/lightdm.conf
        fi
    
        print_center "[*] Eliminando Auto-inicio..." "${DARK_GRAY}"
        rm -f "$TARGET_HOME/.config/autostart/dragonfly_desktop.desktop"
        
        print_center "[*] Eliminando regla Sudoers..." "${DARK_GRAY}"
        rm -f /etc/sudoers.d/010_dragonfly
        
        print_center "[*] Eliminando Responder..." "${DARK_GRAY}"
        rm -rf /opt/Responder
        
        print_center "[+] Desinstalación completada." "${GREEN}"
    else
        print_center "[-] Operación cancelada." "${DARK_GRAY}"
    fi
    sleep 2
}

# Menú interactivo centrado
main_menu() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Por favor, ejecuta este script como root (sudo bash install_desktop.sh)${NC}"
        exit 1
    fi

    while true; do
        draw_banner
        
        local term_width=$(tput cols 2>/dev/null || echo 80)
        local menu_width=50
        local pad_len=$(( (term_width - menu_width) / 2 ))
        [[ $pad_len -lt 0 ]] && pad_len=0
        local padding=$(printf '%*s' "$pad_len" "")

        echo "${padding}1) Instalación Completa (Todo-en-Uno)"
        echo "${padding}2) Instalar Solo Dependencias (APT + Python)"
        echo "${padding}3) Configurar Solo Auto-Inicio y Sudoers"
        echo "${padding}4) Instalar y Configurar Responder"
        echo "${padding}5) Desinstalar Todo"
        echo "${padding}6) Salir"
        echo ""
        
        read -p "${padding}Selecciona una opción [1-6]: " opcion

        case $opcion in
            1)
                instalar_dependencias
                configurar_sistema
                instalar_responder
                print_center "¡INSTALACIÓN DESKTOP COMPLETADA CON ÉXITO!" "${GREEN}"
                echo ""
                print_center "Se recomienda reiniciar el sistema." "${WHITE}"
                read -p "Presiona ENTER para salir..."
                break
                ;;
            2)
                instalar_dependencias
                ;;
            3)
                configurar_sistema
                ;;
            4)
                instalar_responder
                ;;
            5)
                desinstalar_todo
                ;;
            6)
                echo ""
                print_center "Saliendo..." "${DARK_GRAY}"
                exit 0
                ;;
            *)
                echo ""
                print_center "Opción no válida." "${RED}"
                sleep 1
                ;;
        esac
    done
}

main_menu
