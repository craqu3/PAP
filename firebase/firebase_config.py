import firebase_admin
from firebase_admin import credentials, messaging

# Caminho para o ficheiro JSON da tua conta Firebase
cred = credentials.Certificate("firebase_key.json")

firebase_admin.initialize_app(cred)


def send_push_notification(token: str, title: str, body: str, data: dict = None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=token,
        data=data or {}
    )

    response = messaging.send(message)
    return response
