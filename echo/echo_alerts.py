#!/usr/bin/env python3
"""
ECHO alerts - email / SMS / phone-push notifications on detection.

Three channels, all optional, all configured via environment variables so no
secrets live in code:

  Email + SMS (Gmail SMTP):
    ECHO_SMTP_USER   your gmail address
    ECHO_SMTP_PASS   a Gmail *App Password* (not your normal password)
    ECHO_ALERT_TO    comma-separated recipients. For SMS, use your carrier's
                     email-to-text gateway, e.g.:
                       Verizon : 5551234567@vtext.com
                       AT&T    : 5551234567@txt.att.net
                       T-Mobile: 5551234567@tmomail.net
    (optional) ECHO_SMTP_HOST (default smtp.gmail.com), ECHO_SMTP_PORT (587)

  Phone push (ntfy.sh - easiest):
    ECHO_NTFY_TOPIC  topic name, e.g. echo-drone-bryan-9f3x.
    ECHO_NTFY_TOKEN  (optional) access token (tk_...) for a protected topic.
    ECHO_NTFY_SERVER (optional) server URL, default https://ntfy.sh
                     Install the free "ntfy" app, subscribe to that topic.

  Behavior:
    ECHO_ALERT_COOLDOWN  seconds between alerts (default 300 = 5 min)

Anti-spam: a sustained detection only fires ONE alert, then stays quiet for the
cooldown window even if the drone is still overhead.
"""

import os
import smtplib
import ssl
import threading
import time
import urllib.request
from email.message import EmailMessage


def _env_list(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


class AlertManager:
    def __init__(self, block_sec, confirm_sec=2.0):
        self.smtp_host = os.environ.get("ECHO_SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("ECHO_SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("ECHO_SMTP_USER", "")
        self.smtp_pass = os.environ.get("ECHO_SMTP_PASS", "")
        self.recipients = _env_list("ECHO_ALERT_TO")
        self.ntfy_topic = os.environ.get("ECHO_NTFY_TOPIC", "")
        self.ntfy_token = os.environ.get("ECHO_NTFY_TOKEN", "")
        self.ntfy_server = os.environ.get("ECHO_NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        self.cooldown = float(os.environ.get("ECHO_ALERT_COOLDOWN", "300"))

        self.confirm_blocks = max(1, int(confirm_sec / block_sec))
        self.run = 0
        self.last_alert = 0.0

    @property
    def email_enabled(self):
        return bool(self.smtp_user and self.smtp_pass and self.recipients)

    @property
    def push_enabled(self):
        return bool(self.ntfy_topic)

    @property
    def enabled(self):
        return self.email_enabled or self.push_enabled

    def status(self):
        ch = []
        if self.email_enabled:
            ch.append(f"email/SMS -> {len(self.recipients)} recipient(s)")
        if self.push_enabled:
            ch.append(f"ntfy -> {self.ntfy_topic}")
        return ", ".join(ch) if ch else "alerts OFF (no channels configured)"

    # -- trigger logic --
    def process(self, result):
        """Call once per engine result. Fires (async) on a confirmed, non-cooled detection."""
        if result.get("detected"):
            self.run += 1
            now = time.time()
            if self.run == self.confirm_blocks and (now - self.last_alert) > self.cooldown:
                self.last_alert = now
                threading.Thread(target=self._fire, args=(result,), daemon=True).start()
        else:
            self.run = 0

    def _build(self, r):
        bpf = r.get("bpf")
        bearing = f", bearing {r['bearing_deg']} deg" if r.get("bearing_deg") is not None else ""
        multi = " multi-rotor" if r.get("multirotor") else ""
        subject = "ECHO ALERT: drone detected"
        body = (f"ECHO detected a drone acoustic signature.\n\n"
                f"Blade-pass: {bpf} Hz\n"
                f"Implied RPM: ~{r.get('rpm2')} (2-blade) / ~{r.get('rpm3')} (3-blade)\n"
                f"Harmonics: {r.get('harmonics')}   SNR: {r.get('snr_db')} dB\n"
                f"Multi-rotor: {'yes' if r.get('multirotor') else 'no'}{bearing}\n"
                f"Time index: t={r.get('t')}s   ({time.strftime('%Y-%m-%d %H:%M:%S')})\n\n"
                f"(Passive acoustic detection - confirm with RF/visual before acting.)")
        sms = f"ECHO: drone detected. BPF {bpf}Hz,~{r.get('rpm2')}rpm{multi}{bearing}"
        return subject, body, sms

    def _fire(self, r):
        subject, body, sms = self._build(r)
        if self.email_enabled:
            try:
                self._send_email(subject, body, sms)
                print(f"[ALERT] email/SMS sent to {self.recipients}")
            except Exception as e:
                print(f"[ALERT] email failed: {type(e).__name__}: {e}")
        if self.push_enabled:
            try:
                self._send_ntfy(subject, sms)
                print(f"[ALERT] push sent to ntfy topic {self.ntfy_topic}")
            except Exception as e:
                print(f"[ALERT] ntfy failed: {type(e).__name__}: {e}")

    def _send_email(self, subject, body, sms):
        # SMS gateways want short, plain text; email gets the full body.
        for to in self.recipients:
            msg = EmailMessage()
            msg["From"] = self.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            is_sms = any(g in to for g in ("vtext", "txt.att", "tmomail", "msg.fi",
                                           "mms", "sms", "vzwpix"))
            msg.set_content(sms if is_sms else body)
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(self.smtp_user, self.smtp_pass)
                s.send_message(msg)

    def _send_ntfy(self, title, message):
        headers = {"Title": title, "Priority": "high", "Tags": "rotating_light"}
        if self.ntfy_token:
            headers["Authorization"] = f"Bearer {self.ntfy_token}"
        req = urllib.request.Request(
            f"{self.ntfy_server}/{self.ntfy_topic}",
            data=message.encode("utf-8"),
            headers=headers,
        )
        urllib.request.urlopen(req, timeout=15).read()

    def send_test(self):
        """Fire a one-off test alert to verify configuration."""
        fake = {"detected": True, "bpf": 112.0, "rpm2": 3360, "rpm3": 2240,
                "harmonics": 6, "snr_db": 30.0, "multirotor": True,
                "bearing_deg": 90.0, "t": 0.0}
        print(f"[ALERT] sending test via: {self.status()}")
        self._fire(fake)


# ────────────────────────────────────────────────────────────────────
# Multi-channel dispatcher (used by echo_multi.py orchestrator)
# Routes named alert types to channels per echo_cameras.yaml
# alert_routing config. Falls back to the AlertManager above when an
# alert type isn't explicitly routed.
# ────────────────────────────────────────────────────────────────────
_DISPATCHER: "AlertDispatcher | None" = None


class AlertDispatcher:
    """Named-alert dispatcher with per-type channel routing.

    Looks up the alert type in the YAML alert_routing config and sends
    to the configured channels. Channel implementations are pluggable —
    by default this uses the existing AlertManager (email / SMS / ntfy).
    Custom channels (siu_pager / control_center_screen / etc.) can be
    registered via register_channel() — see ARCHITECTURE.md.
    """

    def __init__(self, routing_config: dict | None = None):
        self.routing = routing_config or {}
        self.alert_manager = AlertManager()
        # Map channel-name → handler function. Add yours via register_channel.
        self.channels: dict = {
            "email_alerts_distro":    self._channel_email,
            "siu_pager":              self._channel_ntfy,
            "control_center_screen":  self._channel_log,
            "all_officers_radio":     self._channel_log,
            "warden_email":           self._channel_email,
            "fbi_liaison_email":      self._channel_email,
            "mas_correlation_engine": self._channel_log,
        }

    def dispatch(self, alert_type: str, payload: dict) -> None:
        cfg = self.routing.get(alert_type, {})
        severity = cfg.get("severity", "medium")
        channel_names = cfg.get("channels", ["email_alerts_distro"])
        for name in channel_names:
            handler = self.channels.get(name)
            if handler:
                try:
                    handler(alert_type, severity, payload)
                except Exception as e:
                    print(f"[ALERT] channel {name} failed: {e}")
            else:
                print(f"[ALERT] no handler for channel '{name}' "
                      f"(type={alert_type}, severity={severity})")

    def register_channel(self, name: str, handler) -> None:
        """Register a custom channel — e.g., a Twilio voice call, a
        webhook into the agency's existing incident management system,
        a push to PagerDuty, an RTU pulse to a physical strobe light."""
        self.channels[name] = handler

    # ── built-in channel handlers ──────────────────────────
    def _channel_email(self, alert_type: str, severity: str, payload: dict):
        title = f"[ECHO {severity.upper()}] {alert_type}"
        body = self._format_body(alert_type, payload)
        try:
            self.alert_manager._send_email(title, body)
        except Exception as e:
            print(f"[ALERT email] {e}")

    def _channel_ntfy(self, alert_type: str, severity: str, payload: dict):
        title = f"[ECHO {severity.upper()}] {alert_type}"
        body = self._format_body(alert_type, payload)
        try:
            self.alert_manager._send_ntfy(title, body)
        except Exception as e:
            print(f"[ALERT ntfy] {e}")

    def _channel_log(self, alert_type: str, severity: str, payload: dict):
        # Default for channels with no real implementation yet —
        # PLACEHOLDER for: control_center_screen, all_officers_radio,
        # mas_correlation_engine. Wired up to the SIU/CC integrations
        # when those are available.
        print(f"\n[{severity.upper()} ALERT] {alert_type}")
        for k, v in payload.items():
            print(f"  {k}: {v}")

    def _format_body(self, alert_type: str, payload: dict) -> str:
        return "\n".join(f"{k}: {v}" for k, v in payload.items())


def dispatch_alert(alert_type: str, payload: dict) -> None:
    """Module-level convenience used by echo_multi.py."""
    global _DISPATCHER
    if _DISPATCHER is None:
        # Lazy init from YAML if available; otherwise empty routing
        try:
            import yaml
            from pathlib import Path
            yaml_path = Path(__file__).parent / "echo_cameras.yaml"
            if yaml_path.exists():
                cfg = yaml.safe_load(yaml_path.read_text())
                _DISPATCHER = AlertDispatcher(cfg.get("alert_routing", {}))
            else:
                _DISPATCHER = AlertDispatcher()
        except Exception:
            _DISPATCHER = AlertDispatcher()
    _DISPATCHER.dispatch(alert_type, payload)
