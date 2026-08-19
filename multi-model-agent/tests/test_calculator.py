"""Tests for tools/calculator.py."""
import asyncio

from tools.calculator import calculator


def run(args):
    return asyncio.run(calculator.handler(args))


class TestCalculator:
    def test_add(self):
        result = run({"operation": "add", "a": 2, "b": 3})
        assert "5" in result["content"][0]["text"]
        assert result.get("is_error") is not True

    def test_subtract(self):
        result = run({"operation": "subtract", "a": 10, "b": 4})
        assert "6" in result["content"][0]["text"]

    def test_multiply(self):
        result = run({"operation": "multiply", "a": 6, "b": 7})
        assert "42" in result["content"][0]["text"]

    def test_power(self):
        result = run({"operation": "power", "a": 2, "b": 10})
        assert "1024" in result["content"][0]["text"]

    def test_divide(self):
        result = run({"operation": "divide", "a": 10, "b": 4})
        assert "2.5" in result["content"][0]["text"]

    def test_divide_by_zero_is_error(self):
        result = run({"operation": "divide", "a": 1, "b": 0})
        assert result.get("is_error") is True
        assert "zero" in result["content"][0]["text"].lower()

    def test_unknown_operation_is_error(self):
        result = run({"operation": "modulo", "a": 5, "b": 2})
        assert result.get("is_error") is True
        assert "unknown operation" in result["content"][0]["text"].lower()

    def test_negative_numbers(self):
        result = run({"operation": "add", "a": -5, "b": -3})
        assert "-8" in result["content"][0]["text"]
