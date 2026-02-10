import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_recovery_email(to_email: str, token: str, first_name: str):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")

    reset_link = f"http://localhost:3000/reset-password?token={token}"

    subject = "Recuperação de Password"
    body = f'''
    Olá {first_name},

    Este é o suporte da plataforma Solvex, enviaste um pedido para recuperar a tua conta caso não tenhas sido tu a efetuar este pedido, certifica-te que tens acesso á tua conta e altera a palavra-passe caso necessário 

    Pediste para recuperar a tua password.

    Clica no link abaixo para redefinir a tua password:

    {reset_link}

    Se não foste tu, ignora este email.
    '''

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
