#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Security / OSINT toolkit installer for macOS
# Installs: Shodan, Maltego, SpiderFoot, Sherlock, PhoneInfoga,
#           Recon-NG, BBOT, CloudFox, Nuclei, BloodHound, Caido
# Skipped:  Evilginx3 (offensive 2FA-bypass phishing kit — needs
#           authorized red-team context to install)
# CyberChef — installed locally so it works fully offline (encryption,
# decryption, hashing, encoding all done client-side in your browser).
# Skipped: Evilginx3 (offensive 2FA-bypass phishing kit — needs
#          authorized red-team context to install)
#
# Usage:    bash install_security_tools.sh
#           (or chmod +x then ./install_security_tools.sh)
# ──────────────────────────────────────────────────────────────

set -u
SUCCEEDED=()
FAILED=()
SKIPPED=()

note()  { printf "\n\033[1;34m▶ %s\033[0m\n" "$*"; }
ok()    { printf "  \033[1;32m✓\033[0m %s\n" "$*"; SUCCEEDED+=("$1"); }
fail()  { printf "  \033[1;31m✗\033[0m %s — %s\n" "$1" "$2"; FAILED+=("$1"); }
skip()  { printf "  \033[1;33m⊘\033[0m %s — %s\n" "$1" "$2"; SKIPPED+=("$1"); }

# ── 1. Homebrew ───────────────────────────────────────────────
note "Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  # Try the two standard install locations explicitly
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  else
    echo "  Homebrew not found. Installing…"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
      echo "Brew install failed. Cannot continue." >&2; exit 1; }
    # Pick up the install for both archs
    [[ -x /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
    [[ -x /usr/local/bin/brew     ]] && eval "$(/usr/local/bin/brew shellenv)"
  fi
fi
echo "  brew → $(command -v brew)"

# ── 2. Python tooling (pipx for isolated installs) ────────────
note "Setting up pipx (isolated Python environments)"
brew install pipx 2>/dev/null && pipx ensurepath >/dev/null 2>&1 && ok "pipx" \
  || fail "pipx" "brew install failed"

# Reload PATH so pipx is on it for this session
export PATH="$HOME/.local/bin:$PATH"

# ── 3. OSINT / Recon tools ────────────────────────────────────
note "OSINT / Recon"

pipx install shodan       && ok "Shodan"         || fail "Shodan"        "pipx install failed"
pipx install sherlock-project && ok "Sherlock"   || fail "Sherlock"      "pipx install failed"
pipx install bbot         && ok "BBOT"           || fail "BBOT"          "pipx install failed"
pipx install recon-ng     && ok "Recon-NG"       || fail "Recon-NG"      "pipx install failed"
pipx install spiderfoot   && ok "SpiderFoot"     || fail "SpiderFoot"    "pipx install failed"

# PhoneInfoga — Go binary via dedicated tap
brew install sundowndev/phoneinfoga/phoneinfoga 2>/dev/null \
  && ok "PhoneInfoga" || fail "PhoneInfoga" "brew tap install failed"

# AzureHound — Azure AD data collector (sibling to BloodHound)
if command -v go >/dev/null 2>&1; then
  GOBIN="$HOME/go/bin" go install github.com/bloodhoundad/azurehound/v2@latest 2>&1 | tail -1 \
    && ok "AzureHound → ~/go/bin/azurehound" || fail "AzureHound" "go install failed"
else
  brew install go 2>/dev/null && \
    GOBIN="$HOME/go/bin" go install github.com/bloodhoundad/azurehound/v2@latest 2>&1 | tail -1 \
    && ok "AzureHound" || fail "AzureHound" "go install failed"
fi

# Evilginx3 — GATED on EVILGINX_CONTEXT env var. Offensive 2FA-bypass
# phishing framework. Install only with: authorized red-team engagement,
# CTF competition, or isolated lab VM. NOT for daily-driver Mac.
if [ -n "${EVILGINX_CONTEXT:-}" ]; then
  EG_DIR="$HOME/security_toolkit_bin/evilginx2"
  mkdir -p "$(dirname "$EG_DIR")"
  git clone --depth 1 -q https://github.com/kgretzky/evilginx2.git "$EG_DIR" 2>/dev/null \
    && (cd "$EG_DIR" && go build -o "$HOME/go/bin/evilginx" -ldflags="-s -w" 2>&1 | tail -1) \
    && ok "Evilginx3 → ~/go/bin/evilginx (context: $EVILGINX_CONTEXT)" \
    || fail "Evilginx3" "git clone or build failed"
else
  skip "Evilginx3" "set EVILGINX_CONTEXT=<lab|ctf|engagement-id> before running this script to install"
fi

# CloudFox — Go binary via Bishop Fox tap
brew install bishopfox/cloudfox/cloudfox 2>/dev/null \
  && ok "CloudFox" || fail "CloudFox" "brew tap install failed"

# Maltego — desktop app (heavyweight ~500 MB)
brew install --cask maltego 2>/dev/null \
  && ok "Maltego (desktop)" || fail "Maltego" "brew cask install failed"

# ── 4. Defensive / dual-use ───────────────────────────────────
note "Defensive / dual-use"

# Nuclei — vulnerability scanner from ProjectDiscovery
brew install nuclei 2>/dev/null \
  && ok "Nuclei" || fail "Nuclei" "brew install failed"

# BloodHound — Active Directory analyzer (Community Edition GUI)
brew install --cask bloodhound 2>/dev/null \
  && ok "BloodHound (desktop)" || fail "BloodHound" "brew cask install failed"

# Caido — Burp-Suite-alternative web proxy
brew install --cask caido 2>/dev/null \
  && ok "Caido (desktop)" || fail "Caido" "brew cask install failed"

# ── 5. Skipped / manual ───────────────────────────────────────
note "Skipped / manual"
skip "Evilginx3" "offensive 2FA-bypass kit — re-run with EVILGINX_CONTEXT=<authorization> set"
# CyberChef — self-host the standalone HTML for offline use
note "CyberChef (offline build)"
CYBERCHEF_DIR="$HOME/CyberChef"
mkdir -p "$CYBERCHEF_DIR"
{
  RELEASE_JSON=$(curl -fsSL https://api.github.com/repos/gchq/CyberChef/releases/latest 2>/dev/null) && \
  ASSET_URL=$(printf '%s' "$RELEASE_JSON" | grep -E 'browser_download_url.*CyberChef.*\.zip' | head -1 | cut -d '"' -f 4) && \
  [ -n "$ASSET_URL" ] && \
  curl -fsSL -o /tmp/cyberchef.zip "$ASSET_URL" && \
  unzip -o -q /tmp/cyberchef.zip -d "$CYBERCHEF_DIR" && \
  rm -f /tmp/cyberchef.zip && \
  CC_HTML=$(find "$CYBERCHEF_DIR" -maxdepth 2 -name 'CyberChef_v*.html' | head -1) && \
  [ -n "$CC_HTML" ] && ln -sf "$CC_HTML" "$CYBERCHEF_DIR/CyberChef.html"
} && ok "CyberChef → $CYBERCHEF_DIR/CyberChef.html" \
  || fail "CyberChef" "download/extract failed"

# ── 6. Summary ────────────────────────────────────────────────
note "Done"
printf "  \033[1;32mInstalled (%d):\033[0m %s\n"  "${#SUCCEEDED[@]}" "$(IFS=, ; echo "${SUCCEEDED[*]}")"
printf "  \033[1;31mFailed    (%d):\033[0m %s\n"  "${#FAILED[@]}"    "$(IFS=, ; echo "${FAILED[*]}")"
printf "  \033[1;33mSkipped   (%d):\033[0m %s\n"  "${#SKIPPED[@]}"   "$(IFS=, ; echo "${SKIPPED[*]}")"

cat <<'EOF'

────────────────────────────────────────────────────────────────
NEXT STEPS — most of these tools need API keys or one-time setup
────────────────────────────────────────────────────────────────

Shodan        register at shodan.io for a free API key, then:
              shodan init <YOUR_API_KEY>

SpiderFoot    launches a local web UI on http://127.0.0.1:5001
              spiderfoot -l 127.0.0.1:5001

Recon-NG      first run will prompt to install marketplace modules
              recon-ng

BBOT          first scan creates ~/.bbot config; some modules need keys
              bbot --help

PhoneInfoga   no key needed for basic lookups; some scanners want keys
              phoneinfoga scan -n +15551234567

CloudFox      uses your local AWS profile — needs AWS creds configured
              cloudfox aws --profile default all-checks

Nuclei        update templates after install:
              nuclei -update-templates

Maltego       launch from /Applications — register a free Community
              Edition account on first run

BloodHound    Community Edition runs as a desktop app + bundled Neo4j;
              first launch may take 30s. Use SharpHound on a target AD
              to collect data, then ingest the .zip in BloodHound.

Caido         launch from /Applications — set Firefox/Chrome proxy to
              127.0.0.1:8080, install Caido's CA cert per their docs.

CyberChef     installed offline at ~/CyberChef/CyberChef.html
              open ~/CyberChef/CyberChef.html
              (works fully offline — disconnect Wi-Fi to prove it)

────────────────────────────────────────────────────────────────
USAGE / ETHICS
────────────────────────────────────────────────────────────────
Most of these are dual-use. Use them on assets you own or have
written authorization to test. Scanning, recon, or attacks against
systems you don't own can be a federal crime under the CFAA in the
US (and equivalent laws elsewhere). Stay on your own networks, your
own clients with signed engagements, CTFs, or HackTheBox / TryHackMe
labs.

EOF
EOF
