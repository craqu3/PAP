import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_recovery_email(to_email: str, token: str, first_name: str):
    sender_email = "teu_email@gmail.com"
    sender_password = "A_TUA_APP_PASSWORD"

    reset_link = f"http://localhost:3000/reset-password?token={token}"

    subject = "Recuperação de Password"
    body = f'''
    Olá {first_name}, 

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

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print("Email enviado com sucesso")
    except Exception as e:
        print("Erro ao enviar email:", e)
