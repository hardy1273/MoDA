from scripts.ingest import parse_tags


class TestParseTags:
    def test_pipe_separated(self):
        assert parse_tags("streetwear|minimal|oversized") == [
            "streetwear",
            "minimal",
            "oversized",
        ]

    def test_lowercases_and_strips(self):
        assert parse_tags(" Streetwear | MINIMAL ") == ["streetwear", "minimal"]

    def test_empty_and_none(self):
        assert parse_tags("") == []
        assert parse_tags(None) == []

    def test_skips_blank_segments(self):
        assert parse_tags("a||b|") == ["a", "b"]
