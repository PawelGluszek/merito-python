"""Tests for utils/decorators.py."""

import logging
import pytest

from utils.decorators import log_call, measure_time, retry


class TestMeasureTime:
    def test_preserves_return_value(self):
        @measure_time
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_preserves_function_metadata(self):
        @measure_time
        def my_func():
            """My docstring."""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_logs_timing(self, caplog):
        @measure_time
        def fast():
            return 42

        with caplog.at_level(logging.INFO):
            fast()

        assert any("fast" in record.message and "executed in" in record.message
                    for record in caplog.records)


class TestRetry:
    def test_succeeds_on_first_try(self):
        call_count = 0

        @retry(attempts=3, delay=0)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        @retry(attempts=3, delay=0, exceptions=(ValueError,))
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        assert fail_then_succeed() == "ok"
        assert call_count == 3

    def test_raises_after_exhausting_attempts(self):
        @retry(attempts=2, delay=0, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("fail")

        with pytest.raises(RuntimeError, match="exhausted 2 attempts"):
            always_fail()

    def test_does_not_catch_unspecified_exceptions(self):
        @retry(attempts=3, delay=0, exceptions=(ValueError,))
        def raise_type_error():
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raise_type_error()

    def test_preserves_function_metadata(self):
        @retry(attempts=2)
        def my_func():
            """Docstring."""
            pass

        assert my_func.__name__ == "my_func"


class TestLogCall:
    def test_preserves_return_value(self):
        @log_call
        def multiply(a, b):
            return a * b

        assert multiply(3, 4) == 12

    def test_logs_arguments(self, caplog):
        @log_call
        def greet(name):
            return f"hello {name}"

        with caplog.at_level(logging.DEBUG):
            greet("world")

        assert any("world" in record.message for record in caplog.records)
