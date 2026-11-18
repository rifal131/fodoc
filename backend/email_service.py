"""Layanan Pengiriman Email SMTP FODOC (OTP Registrasi & Notifikasi ACC Panitia).

Konfigurasi melalui `backend/.env`:
- SMTP_HOST=smtp.gmail.com
- SMTP_PORT=587
- SMTP_USER=emailpengirim@gmail.com
- SMTP_PASS=abcd efgh ijkl mnop  (App Password 16 karakter dari Google Account)
- SMTP_FROM=FODOC Universitas Mercu Buana <emailpengirim@gmail.com>
- ADMIN_NOTIFY_EMAIL=emailadmin@gmail.com  (opsional, untuk notifikasi pengajuan Panitia)

Bila SMTP_USER / SMTP_PASS belum diisi, sistem otomatis berjalan dalam mode dev
(mencetak kode OTP di terminal backend agar pengujian tetap berjalan lancar).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger("fodoc.email")


def _get_smtp_config() -> dict[str, Any]:
    host = (os.environ.get("SMTP_HOST") or "smtp.gmail.com").strip()
    port = int((os.environ.get("SMTP_PORT") or "587").strip())
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASS") or "").replace(" ", "").strip()
    sender = (os.environ.get("SMTP_FROM") or user).strip()
    admin_notify = (os.environ.get("ADMIN_NOTIFY_EMAIL") or "").strip()
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sender": sender,
        "admin_notify": admin_notify,
    }


def is_smtp_configured() -> bool:
    cfg = _get_smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


def _send_email(to_email: str, subject: str, plain_body: str, html_body: str | None = None) -> dict[str, Any]:
    cfg = _get_smtp_config()
    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        return {"sent": False, "dev_mode": True}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["sender"] or cfg["user"]
    msg["To"] = to_email
    msg.set_content(plain_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)

    return {"sent": True, "dev_mode": False}


def send_otp_email(to_email: str, otp_code: str, name: str, expires_minutes: int = 5) -> dict[str, Any]:
    """Kirim kode OTP 6 digit ke email mahasiswa."""
    subject = f"Kode Verifikasi FODOC: {otp_code}"
    plain = (
        f"Halo {name},\n\n"
        f"Kode verifikasi pendaftaran akun FODOC — Foto Dokumentasi Universitas Mercu Buana Anda adalah:\n\n"
        f"    {otp_code}\n\n"
        f"Kode ini berlaku selama {expires_minutes} menit. Jangan bagikan kode ini kepada siapa pun.\n\n"
        f"Jika Anda tidak merasa mendaftar di FODOC, abaikan email ini.\n"
        f"— FODOC Universitas Mercu Buana"
    )
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #F5F5F2; padding: 24px; border-radius: 16px; color: #171717;">
      <div style="background: #FFFFFF; border: 1px solid rgba(0,0,0,0.08); border-radius: 14px; padding: 28px;">
        <div style="font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #8F8E8B; margin-bottom: 6px;">
          FODOC · FOTO DOKUMENTASI
        </div>
        <h2 style="margin: 0 0 12px; font-size: 20px; font-weight: 600; color: #171717;">
          Kode Verifikasi Email Anda
        </h2>
        <p style="margin: 0 0 20px; font-size: 14px; line-height: 1.55; color: #52524E;">
          Halo <strong>{name}</strong>, masukkan kode 6 digit berikut untuk menyelesaikan pendaftaran akun mahasiswa Universitas Mercu Buana:
        </p>
        <div style="background: #F5F5F2; border: 1px dashed rgba(0,0,0,0.18); border-radius: 12px; padding: 18px; text-align: center; margin-bottom: 20px;">
          <span style="font-family: 'Courier New', monospace; font-size: 32px; font-weight: 700; letter-spacing: 0.28em; color: #171717;">
            {otp_code}
          </span>
        </div>
        <p style="margin: 0; font-size: 12.5px; color: #6E6D6A; line-height: 1.5;">
          Kode berlaku selama <strong>{expires_minutes} menit</strong>. Demi keamanan akun, jangan bagikan kode ini kepada siapa pun.
        </p>
      </div>
      <div style="text-align: center; font-size: 11px; color: #8F8E8B; margin-top: 14px;">
        FODOC — Foto Dokumentasi · Universitas Mercu Buana
      </div>
    </div>
    """

    if not is_smtp_configured():
        logger.warning("========================================================")
        logger.warning("[EMAIL DEV MODE - SMTP belum diisi di backend/.env]")
        logger.warning("OTP untuk %s (%s): %s", name, to_email, otp_code)
        logger.warning("========================================================")
        return {"sent": False, "dev_mode": True}

    return _send_email(to_email, subject, plain, html)


def send_panitia_request_email_to_admin(
    panitia_name: str,
    panitia_email: str,
    organization: str,
    reason: str = "",
) -> None:
    """Kirim notifikasi email ke Admin saat ada Panitia baru mengajukan akun (jika SMTP & ADMIN_NOTIFY_EMAIL aktif)."""
    cfg = _get_smtp_config()
    to_admin = cfg["admin_notify"]
    if not to_admin or not is_smtp_configured():
        logger.info(
            "[PANITIA REQUEST] %s (%s) — Unit: %s | Menunggu ACC di Admin Panel",
            panitia_name,
            panitia_email,
            organization,
        )
        return

    subject = f"[FODOC] Permohonan ACC Akun Panitia Baru: {panitia_name}"
    plain = (
        f"Halo Admin FODOC,\n\n"
        f"Ada permohonan akun Panitia Acara baru yang menunggu persetujuan (ACC):\n"
        f"- Nama: {panitia_name}\n"
        f"- Email: {panitia_email}\n"
        f"- Asal Kepanitiaan / Unit: {organization}\n"
        f"- Keterangan Acara: {reason or '-'}\n\n"
        f"Silakan buka Admin Panel FODOC untuk menyetujui (ACC) atau menolak permohonan ini."
    )
    try:
        _send_email(to_admin, subject, plain)
    except Exception as exc:
        logger.warning("Gagal kirim notifikasi panitia ke admin (%s): %s", to_admin, exc)


def send_panitia_decision_email(
    to_email: str,
    panitia_name: str,
    organization: str,
    approved: bool,
) -> None:
    """Kirim email pemberitahuan ke Panitia ketika Admin menyetujui (ACC) atau menolak akunnya."""
    if not is_smtp_configured():
        logger.info(
            "[PANITIA %s] %s (%s)",
            "APPROVED" if approved else "REJECTED",
            panitia_name,
            to_email,
        )
        return

    if approved:
        subject = "[FODOC] Akun Panitia Anda Telah Disetujui (ACC)"
        plain = (
            f"Halo {panitia_name},\n\n"
            f"Permohonan akun Panitia Anda ({organization}) di FODOC Universitas Mercu Buana telah DISETUJUI (ACC) oleh Admin.\n"
            f"Anda sekarang sudah dapat masuk (login) menggunakan email {to_email} untuk membuat acara dan mengunggah foto dokumentasi.\n\n"
            f"— FODOC Universitas Mercu Buana"
        )
    else:
        subject = "[FODOC] Status Permohonan Akun Panitia"
        plain = (
            f"Halo {panitia_name},\n\n"
            f"Mohon maaf, permohonan akun Panitia Anda ({organization}) di FODOC Universitas Mercu Buana belum dapat disetujui oleh Admin.\n"
            f"Silakan hubungi Admin jika ini keliru.\n\n"
            f"— FODOC Universitas Mercu Buana"
        )
    try:
        _send_email(to_email, subject, plain)
    except Exception as exc:
        logger.warning("Gagal kirim email keputusan panitia ke %s: %s", to_email, exc)
