"""Tests for output capture and replay buffer."""

from datetime import datetime

from writ.output import ExecutionResult, OutputBuffer


class TestExecutionResult:
    def test_creation(self) -> None:
        result = ExecutionResult(
            command="echo hello",
            returncode=0,
            stdout="hello\n",
            stderr="",
            duration=0.1,
        )
        assert result.command == "echo hello"
        assert result.returncode == 0
        assert result.succeeded is True
        assert isinstance(result.timestamp, datetime)

    def test_failed_result(self) -> None:
        result = ExecutionResult(
            command="false", returncode=1, stdout="", stderr="error\n", duration=0.5
        )
        assert result.succeeded is False


class TestOutputBuffer:
    def test_stores_results(self) -> None:
        buf = OutputBuffer(max_size=5)
        result = ExecutionResult("echo", 0, "out", "", 0.1)
        buf.add(result)
        assert buf.last() is result

    def test_last_returns_none_when_empty(self) -> None:
        buf = OutputBuffer(max_size=5)
        assert buf.last() is None

    def test_last_n_returns_nth_previous(self) -> None:
        buf = OutputBuffer(max_size=5)
        r1 = ExecutionResult("cmd1", 0, "out1", "", 0.1)
        r2 = ExecutionResult("cmd2", 0, "out2", "", 0.1)
        r3 = ExecutionResult("cmd3", 0, "out3", "", 0.1)
        buf.add(r1)
        buf.add(r2)
        buf.add(r3)
        assert buf.last(0) is r3
        assert buf.last(1) is r2
        assert buf.last(2) is r1

    def test_ring_buffer_evicts_oldest(self) -> None:
        buf = OutputBuffer(max_size=2)
        r1 = ExecutionResult("cmd1", 0, "out1", "", 0.1)
        r2 = ExecutionResult("cmd2", 0, "out2", "", 0.1)
        r3 = ExecutionResult("cmd3", 0, "out3", "", 0.1)
        buf.add(r1)
        buf.add(r2)
        buf.add(r3)
        assert buf.last(0) is r3
        assert buf.last(1) is r2
        assert buf.last(2) is None

    def test_last_out_of_range_returns_none(self) -> None:
        buf = OutputBuffer(max_size=5)
        buf.add(ExecutionResult("cmd", 0, "out", "", 0.1))
        assert buf.last(99) is None
