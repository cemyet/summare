"""
Email service for sending transactional emails
"""
import os
import secrets
import string
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Email configuration - can use SMTP, SendGrid, Resend, etc.
EMAIL_FROM = os.getenv("EMAIL_FROM", "cem@summare.se")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp")  # smtp, sendgrid, resend

def generate_password(length: int = 6) -> str:
    """Generate a secure random password - 6 digits"""
    password = ''.join(secrets.choice(string.digits) for _ in range(length))
    return password

def load_email_template(template_name: str, variables: dict) -> str:
    """
    Load an email template and replace variables
    
    Args:
        template_name: Name of the template file (without .html)
    variables: Dictionary of variable_name -> value to replace
    
    Returns:
        Rendered HTML email content
    """
    template_path = Path(__file__).parent.parent / "templates" / "emails" / f"{template_name}.html"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Email template not found: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Replace variables in template {variable_name}
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        template_content = template_content.replace(placeholder, str(value))
    
    return template_content

async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an email using the configured email provider
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content
        
    Returns:
        True if sent successfully, False otherwise
    """
    if EMAIL_PROVIDER == "smtp":
        return await send_email_smtp(to_email, subject, html_content)
    elif EMAIL_PROVIDER == "sendgrid":
        return await send_email_sendgrid(to_email, subject, html_content)
    elif EMAIL_PROVIDER == "resend":
        return await send_email_resend(to_email, subject, html_content)
    else:
        print(f"⚠️ Unknown email provider: {EMAIL_PROVIDER}. Email not sent.")
        print(f"   Would send to: {to_email}")
        print(f"   Subject: {subject}")
        return False

async def send_email_smtp(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via SMTP (supports Microsoft 365 Exchange)"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Microsoft 365 Exchange settings (can be overridden via env vars)
        smtp_host = os.getenv("SMTP_HOST", "smtp.office365.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")  # e.g., cem@summare.se
        smtp_password = os.getenv("SMTP_PASSWORD")  # App password or regular password
        
        if not smtp_user or not smtp_password:
            print("⚠️ SMTP credentials not configured. Email not sent.")
            print("   Set SMTP_USER and SMTP_PASSWORD environment variables")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"✅ Email sent to {to_email} via {smtp_host}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        print(f"❌ SMTP authentication failed: {error_msg}")
        
        # Check for specific Microsoft 365 Security Defaults error
        if "security defaults" in error_msg.lower() or "locked by your organization" in error_msg.lower():
            print("\n🔒 Microsoft 365 Security Defaults is blocking SMTP authentication.")
            print("   This policy blocks basic authentication (SMTP) even with app passwords.")
            print("\n   Solutions:")
            print("   1. Use an alternative email provider (recommended):")
            print("      - Set EMAIL_PROVIDER=resend and add RESEND_API_KEY to .env")
            print("      - Or use SendGrid with EMAIL_PROVIDER=sendgrid")
            print("\n   2. Contact your Microsoft 365 admin to:")
            print("      - Disable Security Defaults (not recommended)")
            print("      - Create a Conditional Access policy allowing SMTP")
            print("      - Or use OAuth/Modern Authentication (requires code changes)")
            print("\n   3. Verify you're using an app password (not regular password):")
            print("      - Go to: https://account.microsoft.com/security")
            print("      - Create new app password for 'Mail'")
            print("      - Use that app password in SMTP_PASSWORD")
        else:
            print("   Check that SMTP_USER and SMTP_PASSWORD are correct")
            print("   For Microsoft 365, you may need an app password")
            print("   Verify the app password at: https://account.microsoft.com/security")
        
        return False
    except Exception as e:
        print(f"❌ Error sending email via SMTP: {str(e)}")
        return False

async def send_email_sendgrid(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via SendGrid"""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        
        api_key = os.getenv("SENDGRID_API_KEY")
        if not api_key:
            print("⚠️ SendGrid API key not configured. Email not sent.")
            return False
        
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        response = sg.send(message)
        print(f"✅ Email sent via SendGrid to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email via SendGrid: {str(e)}")
        return False

async def send_email_resend(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via Resend"""
    try:
        import requests
        
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            print("⚠️ Resend API key not configured. Email not sent.")
            return False
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": EMAIL_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
        )
        
        if response.status_code == 200:
            print(f"✅ Email sent via Resend to {to_email}")
            return True
        else:
            print(f"❌ Resend API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending email via Resend: {str(e)}")
        return False

async def send_password_email(to_email: str, customer_email: str, password: str, login_url: str = "https://www.summare.se") -> bool:
    """
    Send password email to user
    
    Args:
        to_email: Recipient email address
        customer_email: Customer email (used as username)
        password: Generated password
        login_url: URL to login page
        
    Returns:
        True if sent successfully
    """
    try:
        variables = {
            "customer_email": customer_email,
            "password": password,
            "login_url": login_url
        }
        
        html_content = load_email_template("password_email", variables)
        subject = "Välkommen till Summare - Ditt lösenord"
        
        return await send_email(to_email, subject, html_content)
    except Exception as e:
        print(f"❌ Error sending password email: {str(e)}")
        return False

