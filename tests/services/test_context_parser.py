"""Tests for context_parser service."""

from claude_headspace.services.context_parser import parse_context_usage


class TestParseContextUsage:
    """Tests for parse_context_usage function."""

    def test_basic_parse(self):
        text = "[ctx: 22% used, 155k remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 22
        assert result["remaining_tokens"] == "155k"
        assert result["raw"] == "[ctx: 22% used, 155k remaining]"

    def test_high_percentage(self):
        text = "[ctx: 95% used, 10k remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 95
        assert result["remaining_tokens"] == "10k"

    def test_zero_percentage(self):
        text = "[ctx: 0% used, 200k remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 0
        assert result["remaining_tokens"] == "200k"

    def test_full_percentage(self):
        text = "[ctx: 100% used, 0k remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 100
        assert result["remaining_tokens"] == "0k"

    def test_uppercase_k(self):
        text = "[ctx: 50% used, 100K remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["remaining_tokens"] == "100K"

    def test_m_suffix(self):
        text = "[ctx: 10% used, 1.5M remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["remaining_tokens"] == "1.5M"

    def test_decimal_remaining(self):
        text = "[ctx: 75% used, 37.5k remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["remaining_tokens"] == "37.5k"

    def test_with_ansi_codes(self):
        text = "\x1b[32m[ctx: 22% used, 155k remaining]\x1b[0m"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 22
        assert result["remaining_tokens"] == "155k"

    def test_multiline_pane_text(self):
        text = (
            "some output line\n"
            "another line\n"
            "[ctx: 45% used, 110k remaining]\n"
            "$ "
        )
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 45

    def test_no_context_line(self):
        text = "normal terminal output\n$ ls\nfile1.py file2.py"
        result = parse_context_usage(text)
        assert result is None

    def test_empty_string(self):
        result = parse_context_usage("")
        assert result is None

    def test_none_input(self):
        result = parse_context_usage(None)
        assert result is None

    def test_partial_match_missing_bracket(self):
        text = "ctx: 22% used, 155k remaining"
        result = parse_context_usage(text)
        assert result is None

    def test_complex_ansi_codes(self):
        text = "\x1b[1;34m\x1b[0;32m[ctx: 88% used, 24k remaining]\x1b[0m"
        result = parse_context_usage(text)
        assert result is not None
        assert result["percent_used"] == 88

    def test_no_suffix_on_remaining(self):
        text = "[ctx: 50% used, 100 remaining]"
        result = parse_context_usage(text)
        assert result is not None
        assert result["remaining_tokens"] == "100"
