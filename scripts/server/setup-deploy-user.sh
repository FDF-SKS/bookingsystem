#!/usr/bin/env bash
#
# Opsætter en dedikeret, ikke-root deploy-bruger på deploymentserveren.
#
#   sudo ./scripts/server/setup-deploy-user.sh /sti/til/deploy_key.pub
#
# Resultat:
#   * brugeren "deploy" kan ikke logge ind med shell og er IKKE i docker-gruppen
#   * dens SSH-nøgle er låst til én kommando (forced command + restrict)
#   * den kommando starter systemd-unit'en booking-deploy.service som root
#   * unit'en kører /usr/local/sbin/booking-deploy, som ligger fast i /root
#
# CI kan dermed udløse et deploy, men ikke køre vilkårlige kommandoer på hosten.
# Kør scriptet igen for at opdatere nøglen – det er idempotent.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
PUBKEY_FILE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Kør som root (sudo)." >&2
    exit 1
fi

for bin in sudo systemctl journalctl useradd usermod install visudo; do
    command -v "$bin" >/dev/null || { echo "Mangler: $bin" >&2; exit 1; }
done
SUDO_BIN="$(command -v sudo)"

for src in booking-deploy booking-deploy-ssh; do
    [ -f "$SCRIPT_DIR/$src" ] || { echo "Mangler $SCRIPT_DIR/$src" >&2; exit 1; }
done

if [ -n "$PUBKEY_FILE" ] && [ ! -s "$PUBKEY_FILE" ]; then
    echo "Nøglefilen '$PUBKEY_FILE' findes ikke eller er tom." >&2
    exit 1
fi

echo "==> Opretter brugeren $DEPLOY_USER (ingen shell, ingen docker-gruppe)"
if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "/home/$DEPLOY_USER" \
        --shell /usr/sbin/nologin "$DEPLOY_USER"
else
    # Sørg for at en eksisterende bruger ikke har shell-adgang.
    usermod --shell /usr/sbin/nologin "$DEPLOY_USER"
fi
chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER"
chmod 0755 "/home/$DEPLOY_USER"

echo "==> Installerer deploy-scripts i /usr/local/sbin"
install -o root -g root -m 0755 "$SCRIPT_DIR/booking-deploy" /usr/local/sbin/booking-deploy
install -o root -g root -m 0755 "$SCRIPT_DIR/booking-deploy-ssh" /usr/local/sbin/booking-deploy-ssh

echo "==> Opretter systemd-unit booking-deploy.service"
cat > /etc/systemd/system/booking-deploy.service <<'UNIT'
[Unit]
Description=Deploy booking-system fra Docker Hub
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/booking-deploy
TimeoutStartSec=20min
SyslogIdentifier=booking-deploy
UNIT

# Ingen [Install]-sektion: unit'en må IKKE starte ved boot, kun når CI beder om det.
systemctl daemon-reload

echo "==> Tilføjer sudo-regel for KUN wrapper-scriptet"
SUDOERS_FILE=/etc/sudoers.d/booking-deploy
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/booking-deploy-ssh\n' "$DEPLOY_USER" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE"

if [ -n "$PUBKEY_FILE" ]; then
    echo "==> Installerer SSH-nøgle med forced command"
    install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0700 "/home/$DEPLOY_USER/.ssh"
    {
        printf 'restrict,command="%s -n /usr/local/sbin/booking-deploy-ssh" ' "$SUDO_BIN"
        tr -d '\r\n' < "$PUBKEY_FILE"
        printf '\n'
    } > "/home/$DEPLOY_USER/.ssh/authorized_keys"
    chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
    chmod 0600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
    echo "    Nøglen kan herefter kun udløse booking-deploy-ssh."
fi

cat <<INFO

Færdig. Næste skridt:

1. Test som root på serveren:
     sudo -u $DEPLOY_USER $SUDO_BIN -n /usr/local/sbin/booking-deploy-ssh

2. I GitHub: sæt repository-secrets
     HETZNER_HOST              = serverens hostname/IP
     HETZNER_SSH_KEY           = den PRIVATE nøgle der hører til den installerede pubkey
     HETZNER_HOST_FINGERPRINT  = SHA256-fingerprint på serverens host key
   Workflowet logger ind som "$DEPLOY_USER", ikke root.

3. Rotér nøglen: slet den gamle root-nøgle i /root/.ssh/authorized_keys,
   når det nye deploy virker.

INFO
