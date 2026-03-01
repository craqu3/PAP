import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_recovery_email(to_email: str, token: str, first_name: str):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")

    print(f"EmaiL: {sender_email}")
    reset_link = f"http://localhost:3000/reset-password?token={token}"

    subject = "Recuperação de Password"
    body = f'''
    Olá {first_name},

    Este é o suporte da plataforma Solvex, enviaste um pedido para recuperar a tua conta caso não tenhas sido tu a efetuar este pedido, certifica-te que tens acesso á tua conta e altera a palavra-passe caso necessário 


    Clica no link abaixo para redefinir a tua password:

    {reset_link}

    '''

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
