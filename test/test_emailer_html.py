from notifications import emailer


class SMTPFalso:
    ultimo_mensaje = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, *args):
        pass

    def send_message(self, mensaje):
        SMTPFalso.ultimo_mensaje = mensaje


def configurar(monkeypatch):
    valores = {"EMAIL_ENABLED": "true", "SMTP_HOST": "smtp.test",
               "SMTP_PORT": "587", "SMTP_USER": "user", "SMTP_PASSWORD": "pass",
               "EMAIL_FROM": "from@test", "EMAIL_TO": "to@test"}
    for clave, valor in valores.items():
        monkeypatch.setenv(clave, valor)
    monkeypatch.setattr(emailer.smtplib, "SMTP", SMTPFalso)


def test_email_texto_sigue_siendo_compatible(monkeypatch):
    configurar(monkeypatch)
    assert emailer.enviar_email("Asunto", "Texto") is True
    assert SMTPFalso.ultimo_mensaje.get_content_type() == "text/plain"


def test_email_html_alternativo_con_imagen_cid(monkeypatch, tmp_path):
    configurar(monkeypatch)
    imagen = tmp_path / "chart.png"
    imagen.write_bytes(b"imagen")
    assert emailer.enviar_email(
        "Asunto", "Texto", '<img src="cid:grafico">', {"grafico": imagen}
    ) is True
    mensaje = SMTPFalso.ultimo_mensaje
    tipos = [parte.get_content_type() for parte in mensaje.walk()]
    assert "text/plain" in tipos
    assert "text/html" in tipos
    assert "image/png" in tipos
