#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Security / OSINT toolkit installer for Linux
# (Debian/Ubuntu family — apt-based)
#
# Same tool list as install_mac.sh, adapted for Linux:
#   Shodan, Sherlock, BBOT, Recon-NG (git), SpiderFoot (git),
#   PhoneInfoga (pre-built binary), Nuclei (go), CloudFox (go),
#   CyberChef (offline standalone HTML)
#
# Skipped:
#   Maltego, BloodHound, Caido — desktop GUI apps (use deb installers
#       from each project's site if you have a desktop environment)
#   Evilginx3 — offensive 2FA-bypass kit; install only with authorized
#       red-team context
#
# Usage:    bash install_linux.sh
# ──────────────────────────────────────────────────────────────

set -u
TOOLS_DIR="$HOME/security_toolkit_bin"
mkdir -p "$TOOLS_DIR"

SUCCEEDED=(); FAILED=(); SKIPPED=()
note()  { printf "\n\033[1;34m▶ %s\033[0m\n" "$*"; }
ok()    { printf "  \033[1;32m✓\033[0m %s\n" "$*"; SUCCEEDED+=("$1"); }
fail()  { printf "  \033[1;31m✗\033[0m %s — %s\n" "$1" "$2"; FAILED+=("$1"); }
skip()  { printf "  \033[1;33m⊘\033[0m %s — %s\n" "$1" "$2"; SKIPPED+=("$1"); }

# ── 1. OS sanity ──────────────────────────────────────────────
note "OS check"
if ! command -v apt-get >/dev/null 2>&1; then
  echo "  This script is for Debian/Ubuntu. Adapt the apt-get calls for your distro." >&2
fi

# ── 2. Apt prerequisites ──────────────────────────────────────
note "apt prerequisites"
sudo apt-get update -qq 2>/dev/null || apt-get update -qq 2>/dev/null
sudo apt-get install -y -qq python3 python3-pip python3-venv pipx git curl unzip jq golang-go 2>/dev/null \
  || apt-get install -y -qq python3 python3-pip python3-venv pipx git curl unzip jq golang-go 2>/dev/null \
  && ok "apt deps" || fail "apt deps" "apt-get install failed (need sudo?)"

export PATH="$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$TOOLS_DIR:$PATH"
pipx ensurepath >/dev/null 2>&1 || true

# ── 3. Python tools (pipx) ────────────────────────────────────
note "Python tools (pipx isolated)"
pipx install --quiet shodan          && pipx inject --quiet shodan setuptools && ok "Shodan"    || fail "Shodan"    "pipx install failed"
pipx install --quiet sherlock-project && ok "Sherlock"                       || fail "Sherlock"  "pipx install failed"
pipx install --quiet bbot            && ok "BBOT"                            || fail "BBOT"      "pipx install failed"

# Recon-NG and SpiderFoot are not on PyPI as installable packages — clone instead
note "Cloned-from-git tools"
git clone --depth 1 -q https://github.com/lanmaster53/recon-ng.git "$TOOLS_DIR/recon-ng" 2>/dev/null \
  && pip3 install --quiet -r "$TOOLS_DIR/recon-ng/REQUIREMENTS" 2>&1 | tail -1 \
  && ok "Recon-NG → $TOOLS_DIR/recon-ng/recon-ng" || fail "Recon-NG" "git clone or pip install failed"

git clone --depth 1 -q https://github.com/smicallef/spiderfoot.git "$TOOLS_DIR/spiderfoot" 2>/dev/null \
  && pip3 install --quiet -r "$TOOLS_DIR/spiderfoot/requirements.txt" 2>&1 | tail -1 \
  && ok "SpiderFoot → $TOOLS_DIR/spiderfoot/sf.py" || fail "SpiderFoot" "git clone or pip install failed"

# ── 4. Go binaries (compiled) ─────────────────────────────────
note "Go tools"
GOBIN=$HOME/go/bin go install -ldflags="-s -w" github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest 2>&1 | tail -1 \
  && ok "Nuclei" || fail "Nuclei" "go install failed"
GOBIN=$HOME/go/bin go install -ldflags="-s -w" github.com/BishopFox/cloudfox@latest 2>&1 | tail -1 \
  && ok "CloudFox" || fail "CloudFox" "go install failed (large build, may take a few min)"

# ── 5. PhoneInfoga (pre-built binary — go install fails due to embedded JS) ──
note "PhoneInfoga (pre-built binary)"
PI_VER=$(curl -sI https://github.com/sundowndev/phoneinfoga/releases/latest \
         | grep -i '^location:' | sed -E 's|.*/tag/v?([^[:space:]]+).*|\1|' | tr -d '\r\n')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ARCH_TAG="x86_64" ;;
  aarch64) ARCH_TAG="arm64"  ;;
  *)       ARCH_TAG="$ARCH"  ;;
esac
PI_URL="https://github.com/sundowndev/phoneinfoga/releases/download/v${PI_VER}/phoneinfoga_Linux_${ARCH_TAG}.tar.gz"
curl -fsSL -o /tmp/pi.tar.gz "$PI_URL" \
  && tar -xzf /tmp/pi.tar.gz -C "$TOOLS_DIR" phoneinfoga \
  && chmod +x "$TOOLS_DIR/phoneinfoga" \
  && rm -f /tmp/pi.tar.gz \
  && ok "PhoneInfoga $PI_VER → $TOOLS_DIR/phoneinfoga" || fail "PhoneInfoga" "binary download failed"

# ── 6. CyberChef (offline standalone HTML) ────────────────────
note "CyberChef (offline)"
CC_DIR="$TOOLS_DIR/cyberchef"
mkdir -p "$CC_DIR"
CC_TAG=$(curl -sI https://github.com/gchq/CyberChef/releases/latest \
         | grep -i '^location:' | sed -E 's|.*/tag/v([^[:space:]]+).*|\1|' | tr -d '\r\n')
# CyberChef releases use hashed asset names (CyberChef_<hash>.zip); scrape the
# expanded_assets page to find the actual download URL
CC_PATH=$(curl -fsSL "https://github.com/gchq/CyberChef/releases/expanded_assets/v${CC_TAG}" \
          | grep -Eo 'href="[^"]*CyberChef_[^"]*\.zip"' | head -1 | sed 's/href="//; s/"$//')
curl -fsSL -o /tmp/cc.zip "https://github.com${CC_PATH}" \
  && unzip -q -o /tmp/cc.zip -d "$CC_DIR" \
  && ln -sf "$(find "$CC_DIR" -maxdepth 2 -name 'CyberChef_*.html' | head -1)" "$CC_DIR/CyberChef.html" \
  && rm -f /tmp/cc.zip \
  && ok "CyberChef v$CC_TAG → $CC_DIR/CyberChef.html" || fail "CyberChef" "download failed"

# ── 7. Skipped ────────────────────────────────────────────────
note "Skipped"
skip "Maltego"   "desktop GUI app — install the .deb from maltego.com if you have a DE"
skip "BloodHound" "desktop GUI app — see github.com/SpecterOps/BloodHound for Linux installer"
skip "Caido"     "desktop GUI app — install from caido.io"
skip "Evilginx3" "offensive 2FA-bypass kit — install only with authorized red-team context"

# ── 8. Summary ────────────────────────────────────────────────
note "Done"
printf "  \033[1;32mInstalled (%d):\033[0m %s\n" "${#SUCCEEDED[@]}" "$(IFS=, ; echo "${SUCCEEDED[*]}")"
printf "  \033[1;31mFailed    (%d):\033[0m %s\n" "${#FAILED[@]}"    "$(IFS=, ; echo "${FAILED[*]}")"
printf "  \033[1;33mSkipped   (%d):\033[0m %s\n" "${#SKIPPED[@]}"   "$(IFS=, ; echo "${SKIPPED[*]}")"

cat <<EOF

Add these to your PATH (already in this session's PATH):
  export PATH="\$HOME/.local/bin:\$HOME/go/bin:$TOOLS_DIR:\$PATH"

Persist by adding that line to ~/.bashrc or ~/.zshrc.

CyberChef offline: open $TOOLS_DIR/cyberchef/CyberChef.html in any browser.
                   Works fully offline (disconnect Wi-Fi to prove it).

Shodan:    needs API key. Get one free at shodan.io, then 'shodan init <KEY>'.
Nuclei:    run 'nuclei -update-templates' once after install.
Recon-NG:  run '$TOOLS_DIR/recon-ng/recon-ng' to launch (marketplace inside).
SpiderFoot: run 'python3 $TOOLS_DIR/spiderfoot/sf.py -l 127.0.0.1:5001' for web UI.
EOF
