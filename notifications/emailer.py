import os
import smtplib
import mimetypes
from pathlib import Path

from email.message import EmailMessage

from dotenv import load_dotenv


load_dotenv()


def enviar_email(
    asunto,
    contenido,
    html=None,
    inline_images=None
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

    if html:
        mensaje.add_alternative(
            html,
            subtype="html"
        )

        parte_html = mensaje.get_payload()[-1]

        for cid, ruta in (inline_images or {}).items():
            try:
                ruta = Path(ruta)
                tipo, _ = mimetypes.guess_type(ruta.name)
                principal, subtipo = (
                    tipo.split("/", 1)
                    if tipo and "/" in tipo
                    else ("application", "octet-stream")
                )
                parte_html.add_related(
                    ruta.read_bytes(),
                    maintype=principal,
                    subtype=subtipo,
                    cid=f"<{cid}>",
                    filename=ruta.name
                )
            except OSError as error:
                print(f"No se pudo adjuntar imagen inline {ruta}: {error}")


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
