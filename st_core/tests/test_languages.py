from core.languages import detect_language, normalize_language


class TestLanguageDetection:
    def test_normalize_full_code(self):
        assert normalize_language("en-US") == "en"

    def test_normalize_none(self):
        assert normalize_language(None) == "en"

    def test_normalize_unsupported(self):
        assert normalize_language("fr") == "en"

    def test_detect_from_form(self):
        assert detect_language(form_lang="it") == "it"

    def test_detect_accept_language(self):
        assert detect_language(form_lang=None, accept_language="es-MX,en;q=0.9") == "es"

    def test_detect_fallback(self):
        assert detect_language(form_lang=None, accept_language=None) == "en"

    def test_detect_form_overrides_accept(self):
        assert detect_language(form_lang="sr", accept_language="en") == "sr"
