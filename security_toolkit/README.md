# Security / OSINT Toolkit

Reproducible installs for the security & recon toolset, organized by platform.
Use this when setting up a new machine (Mac, Linux box, or fresh dev env) so
the same tools land in the same places.

## What's in the box

| Tool | Category | Use |
|---|---|---|
| **Shodan** | OSINT | Internet-connected device search. Free API key required. |
| **Sherlock** | OSINT | Username enumeration across 400+ social sites. |
| **PhoneInfoga** | OSINT | Phone number recon — carrier, geo, footprint. |
| **Recon-NG** | OSINT framework | Modular reconnaissance with a marketplace of plugins. |
| **SpiderFoot** | OSINT framework | Automated multi-source OSINT with a web UI on `:5001`. |
| **BBOT** | OSINT framework | Bug-bounty / attack-surface automation. |
| **CloudFox** | Cloud recon | AWS attack-surface enumeration (uses your AWS profile). |
| **Nuclei** | Vuln scanner | Template-based vulnerability scanning of your own infra. |
| **CyberChef** | Data analysis | Browser-based encoding/decoding, encryption, parsing, forensics. |

## What's NOT in the box, and why

| Tool | Why skipped |
|---|---|
| **Maltego** | Desktop GUI app (~500 MB) — install per-platform when needed |
| **BloodHound** | Desktop GUI for Active Directory analysis — install when needed |
| **Caido** | Desktop GUI web proxy (Burp alternative) — install when needed |
| **Evilginx3** | Offensive 2FA-bypass phishing kit. Install only with authorized red-team context (CTF, signed pentest engagement, isolated lab). |

## Install

### macOS

```bash
bash install_mac.sh
```

Uses Homebrew. Installs the CLI tools via pipx + brew taps, and the three
GUI apps (Maltego, BloodHound, Caido) via brew cask. CyberChef is downloaded
as a standalone offline HTML to `~/CyberChef/`.

### Linux (Debian/Ubuntu)

```bash
bash install_linux.sh
```

Uses apt + pipx + go install + direct binary downloads. Skips the GUI apps
(you'd install those manually if you have a desktop environment). CyberChef
downloads to `~/security_toolkit_bin/cyberchef/`.

## Ethics / legal note

These tools are dual-use. Almost all of them are legal to *install*. Using
them on systems you don't own or don't have written authorization to test
can be a federal crime in the US (CFAA) and equivalent in most jurisdictions.

Legitimate use:
- Your own infrastructure (scan your own servers, audit your own AD)
- Signed pentest engagements with written scope
- CTF / HackTheBox / TryHackMe lab environments
- Public-internet OSINT against publicly available data
- Bug bounty programs that explicitly invite testing on listed scopes

Not legitimate:
- Random services you found interesting
- Anyone you have a dispute with
- "Just to see if it works" against production systems you don't own

## Defending against this class of tooling

The reason to learn offensive tools as a defender is to know what to block.
Notes on what each enables, and the defense:

| Attack | Tool | Defense |
|---|---|---|
| Lookalike-domain phishing → MFA bypass | (Evilginx3 — not installed) | **Passkeys / FIDO2 / WebAuthn**. The browser binds auth to the actual origin URL, so a lookalike domain fails the protocol check. The only real defense. |
| Username enumeration on your auth endpoints | Sherlock-style scanners | Don't reveal "user exists" on login failures. Same error message whether the email exists or not. |
| Active scanning of your public surface | Nuclei | Keep dependencies patched. Run Nuclei against yourself first, weekly. |
| Cloud (AWS) attack surface | CloudFox | Least-privilege IAM, no overly-permissive S3 buckets, no public RDS, key rotation. Use AWS Config + GuardDuty. |
| OSINT against your employees / company | Maltego, SpiderFoot, BBOT | Limit what employees post publicly. DMARC/SPF/DKIM on email. Watch for lookalike-domain registrations. |
| Phone-number-based social engineering | PhoneInfoga | Don't tie 2FA to SMS for high-value accounts. Don't publish work cell numbers. |

## Notes on the offline CyberChef

CyberChef is open-sourced by GCHQ (UK signals intelligence agency) and is
~75 MB of static HTML + JS. All processing is client-side — your input
never leaves the browser even on the hosted version at
`https://gchq.github.io/CyberChef/`.

The install script downloads the latest release zip from
`github.com/gchq/CyberChef/releases/latest` and places the standalone HTML
in `~/CyberChef/CyberChef.html` (Mac) or
`~/security_toolkit_bin/cyberchef/CyberChef.html` (Linux). Open it in any
browser, then disconnect from Wi-Fi to prove it works offline.

It is **not** a code-protection or DRM mechanism. Use it for learning crypto,
decoding obfuscated data, building analysis pipelines, parsing forensic
artifacts.
