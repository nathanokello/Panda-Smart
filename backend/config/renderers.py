from rest_framework.renderers import BaseRenderer


class PlainTextRenderer(BaseRenderer):
    """Render USSD callbacks as the plain text Africa's Talking expects."""

    media_type = "text/plain"
    format = "txt"
    charset = "utf-8"

    def render(self, data, media_type=None, renderer_context=None):
        return str(data).encode(self.charset)
