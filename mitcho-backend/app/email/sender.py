"""
Email sending via Resend API.
Handles: welcome email, monthly report notification, alert emails.
Free tier: 100 emails/day, 3000/month.
"""
import logging
from typing import Optional

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def _init_resend():
    resend.api_key = settings.RESEND_API_KEY


WELCOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Helvetica Neue', sans-serif; max-width: 600px; margin: auto; background: #f9fafb; padding: 24px;">
  <div style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: #006432; padding: 32px 40px;">
      <h1 style="color: white; margin: 0; font-size: 24px; letter-spacing: -0.5px;">MITCHÔ</h1>
      <p style="color: rgba(255,255,255,0.7); margin: 8px 0 0; font-size: 13px;">Intelligence Publique · Bénin</p>
    </div>
    <div style="padding: 40px;">
      <h2 style="color: #0a1e14; font-size: 20px; margin: 0 0 16px;">Bienvenue, {name} !</h2>
      <p style="color: #374151; line-height: 1.6;">
        Votre compte MITCHÔ est créé. Vous avez désormais accès aux rapports d'analyse mensuels
        sur la sécurité alimentaire au Bénin.
      </p>
      {subscription_note}
      <a href="https://mitchobenin.org/tendances.html"
         style="display: inline-block; margin-top: 24px; background: #006432; color: white;
                padding: 14px 28px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;">
        Accéder aux prévisions
      </a>
    </div>
    <div style="padding: 24px 40px; border-top: 1px solid #e5e7eb;">
      <p style="color: #9ca3af; font-size: 12px; margin: 0;">
        Vous recevez cet email car vous vous êtes inscrit sur MITCHÔ.<br>
        Pour vous désabonner, répondez à cet email avec "STOP".
      </p>
    </div>
  </div>
</body>
</html>
"""

MONTHLY_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Helvetica Neue', sans-serif; max-width: 600px; margin: auto; background: #f9fafb; padding: 24px;">
  <div style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: #006432; padding: 32px 40px;">
      <p style="color: rgba(255,255,255,0.6); font-size: 12px; margin: 0 0 8px; text-transform: uppercase; letter-spacing: 1px;">Rapport Mensuel</p>
      <h1 style="color: white; margin: 0; font-size: 22px;">MITCHÔ — {month_label}</h1>
    </div>
    <div style="padding: 40px;">
      <p style="color: #374151; line-height: 1.6; font-size: 14px;">
        Le rapport d'analyse de la sécurité alimentaire au Bénin pour <strong>{month_label}</strong> est disponible.
      </p>
      <div style="background: #f0f8f4; border-radius: 8px; padding: 20px; margin: 24px 0; border-left: 3px solid #10b981;">
        <p style="color: #0a1e14; font-size: 13px; margin: 0; font-weight: 600;">Résumé :</p>
        <p style="color: #374151; font-size: 13px; margin: 8px 0 0; line-height: 1.6;">{summary}</p>
      </div>
      <a href="https://mitchobenin.org/tendances.html"
         style="display: inline-block; background: #006432; color: white;
                padding: 14px 28px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;">
        Télécharger le rapport complet (PDF)
      </a>
    </div>
    <div style="padding: 24px 40px; border-top: 1px solid #e5e7eb;">
      <p style="color: #9ca3af; font-size: 12px; margin: 0;">
        MITCHÔ — Intelligence Publique pour la Sécurité Alimentaire au Bénin<br>
        Pour vous désabonner, répondez avec "STOP".
      </p>
    </div>
  </div>
</body>
</html>
"""


def send_welcome_email(to_email: str, name: str, is_subscribed: bool = False) -> bool:
    if not settings.RESEND_API_KEY:
        logger.warning("[Email] RESEND_API_KEY not set — skipping welcome email")
        return False
    try:
        _init_resend()
        sub_note = (
            '<p style="color: #10b981; font-size: 13px; margin: 16px 0 0;">'
            'Vous êtes abonné aux alertes mensuelles par email.</p>'
            if is_subscribed else ""
        )
        resend.Emails.send({
            "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
            "to": [to_email],
            "subject": "Bienvenue sur MITCHÔ",
            "html": WELCOME_TEMPLATE.format(name=name, subscription_note=sub_note),
        })
        logger.info(f"[Email] Welcome sent to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"[Email] Failed to send welcome to {to_email}: {exc}")
        return False


def send_monthly_report_notification(
    subscribers: list[dict],
    month_label: str,
    summary: str,
) -> int:
    """
    Sends the monthly report notification to all subscribers.
    subscribers: [{"email": str, "name": str}]
    Returns number of emails sent successfully.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("[Email] RESEND_API_KEY not set — skipping monthly emails")
        return 0

    _init_resend()
    sent = 0
    html = MONTHLY_REPORT_TEMPLATE.format(month_label=month_label, summary=summary[:400])

    for sub in subscribers:
        try:
            resend.Emails.send({
                "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
                "to": [sub["email"]],
                "subject": f"MITCHÔ — Rapport {month_label} disponible",
                "html": html,
            })
            sent += 1
        except Exception as exc:
            logger.error(f"[Email] Failed to send to {sub['email']}: {exc}")

    logger.info(f"[Email] Monthly report sent to {sent}/{len(subscribers)} subscribers")
    return sent
