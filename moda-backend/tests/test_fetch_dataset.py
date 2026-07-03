from scripts.fetch_dataset import hex_to_color_tag, photo_row


class TestHexToColorTag:
    def test_maps_dark_hex_to_black(self):
        assert hex_to_color_tag("#111111") == ["black"]

    def test_maps_light_hex_to_white(self):
        assert hex_to_color_tag("#fafafa") == ["white"]

    def test_maps_midtone_to_grey(self):
        assert hex_to_color_tag("#808080") == ["grey"]

    def test_invalid_or_missing_hex(self):
        assert hex_to_color_tag(None) == []
        assert hex_to_color_tag("red") == []
        assert hex_to_color_tag("#abc") == []
        assert hex_to_color_tag("#zzzzzz") == []


class TestPhotoRow:
    def _photo(self, **overrides):
        photo = {
            "id": "abc123",
            "urls": {"regular": "https://images.unsplash.com/photo-abc123?w=1080"},
            "alt_description": "man in black hoodie standing on street",
            "color": "#0c0c0c",
            "user": {"name": "Jane Doe"},
            "links": {"html": "https://unsplash.com/photos/abc123"},
        }
        photo.update(overrides)
        return photo

    def test_builds_ingest_ready_row(self):
        row = photo_row(self._photo(), ["streetwear"], ["everyday"], "streetwear outfit")
        assert row["image"] == "https://images.unsplash.com/photo-abc123?w=1080"
        assert row["caption"] == "man in black hoodie standing on street"
        assert row["style_tags"] == "streetwear"
        assert row["color_tags"] == "black"
        assert row["occasion_tags"] == "everyday"
        assert "Jane Doe" in row["credit"]

    def test_falls_back_to_query_when_no_description(self):
        row = photo_row(
            self._photo(alt_description=None, description=None),
            ["minimal"],
            ["everyday"],
            "minimal outfit",
        )
        assert row["caption"] == "minimal outfit"

    def test_multiple_tags_pipe_joined(self):
        row = photo_row(self._photo(), ["streetwear", "oversized"], ["everyday"], "q")
        assert row["style_tags"] == "streetwear|oversized"
