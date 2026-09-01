import os
import smtplib

from email.message import EmailMessage

from dotenv import load_dotenv


load_dotenv()


def enviar_email(
    asunto,
    contenido
):
    """
    Envía un correo usando SMTP.
    """

    enabled = (
        os.getenv(
            "EMAIL_ENABLED",
            "false"
        ).lower()
        == "true"
    )

    if not enabled:

        print(
            "Email desactivado en .env"
        )

        return False


    smtp_host = os.getenv(
        "SMTP_HOST"
    )

    smtp_port = int(
        os.getenv(
            "SMTP_PORT",
            "587"
        )
    )

    smtp_user = os.getenv(
        "SMTP_USER"
    )

    smtp_password = os.getenv(
        "SMTP_PASSWORD"
    )

    email_from = os.getenv(
        "EMAIL_FROM"
    )

    email_to = os.getenv(
        "EMAIL_TO"
    )


    variables = {
        "SMTP_HOST": smtp_host,
        "SMTP_USER": smtp_user,
        "SMTP_PASSWORD": smtp_password,
        "EMAIL_FROM": email_from,
        "EMAIL_TO": email_to
    }


    faltantes = [
        nombre
        for nombre, valor
        in variables.items()
        if not valor
    ]


    if faltantes:

        raise ValueError(
            "Faltan variables de email: "
            + ", ".join(faltantes)
        )


    mensaje = EmailMessage()

    mensaje["Subject"] = asunto

    mensaje["From"] = email_from

    mensaje["To"] = email_to

    mensaje.set_content(
        contenido
    )


    with smtplib.SMTP(
        smtp_host,
        smtp_port,
        timeout=30
    ) as servidor:

        servidor.ehlo()

        servidor.starttls()

        servidor.ehlo()

        servidor.login(
            smtp_user,
            smtp_password
        )

        servidor.send_message(
            mensaje
        )


    print(
        f"Correo enviado a {email_to}"
    )

    return True