"""Tests for the pure-logic heuristic classifier in router.py (no API calls)."""
import pytest

from router import classify_with_heuristic


class TestFastSignals:
    def test_short_what_is_is_fast(self):
        assert classify_with_heuristic("What is the capital of France?") == "fast"

    def test_define_is_fast(self):
        assert classify_with_heuristic("Define osmosis") == "fast"

    def test_convert_is_fast(self):
        assert classify_with_heuristic("Convert 10 miles to km") == "fast"

    def test_case_insensitive(self):
        assert classify_with_heuristic("WHAT IS 2+2?") == "fast"

    def test_long_what_is_not_fast(self):
        # Starts with "what is" but exceeds the 60-char cutoff -> not an obvious fast case
        long_prompt = "What is " + ("a very long explanation of quantum mechanics " * 3)
        assert len(long_prompt) >= 60
        assert classify_with_heuristic(long_prompt) != "fast"


class TestDeepSignals:
    def test_architect_is_deep(self):
        assert classify_with_heuristic("Help me architect a new microservices system") == "deep"

    def test_design_a_system_is_deep(self):
        assert classify_with_heuristic("Design a system for handling 1M requests/sec") == "deep"

    def test_root_cause_is_deep(self):
        assert classify_with_heuristic("What's the root cause of this memory leak?") == "deep"

    def test_tradeoff_with_hyphen_variant(self):
        assert classify_with_heuristic("What are the trade-offs of microservices?") == "deep"
        assert classify_with_heuristic("What are the tradeoffs of microservices?") == "deep"

    def test_very_long_prompt_is_deep(self):
        assert classify_with_heuristic("x" * 1201) == "deep"

    def test_exactly_1200_chars_not_forced_deep(self):
        # len() > 1200 is the threshold, so exactly 1200 should not trigger on length alone
        prompt = "a" * 1200
        assert classify_with_heuristic(prompt) is None


class TestAmbiguous:
    def test_medium_prompt_returns_none(self):
        assert classify_with_heuristic("Summarize this paragraph for me please") is None

    def test_empty_string_returns_none(self):
        assert classify_with_heuristic("") is None

    def test_whitespace_only_returns_none(self):
        assert classify_with_heuristic("   \n\t  ") is None
