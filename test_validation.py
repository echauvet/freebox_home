"""  python -m pytest test_validation.py -k "port" -v
"""

import pytest
from .validation import (
    validate_port,
    validate_scan_interval,
    validate_reboot_interval,
    validate_reboot_time,
    validate_temp_refresh_interval,
    validate_temp_refresh_duration,
    validate_host,
    get_validation_bounds,
)


class TestValidatePort:
    """Test suite for validate_port function."""

    def test_valid_port_minimum(self):
        """Test minimum valid port (1)."""
        assert validate_port(1) == 1

    def test_valid_port_maximum(self):
        """Test maximum valid port (65535)."""
        assert validate_port(65535) == 65535

    def test_valid_port_middle(self):
        """Test middle-range valid port (443)."""
        assert validate_port(443) == 443

    def test_valid_port_string(self):
        """Test string conversion to port."""
        assert validate_port("8080") == 8080

    def test_invalid_port_zero(self):
        """Test port 0 (invalid)."""
        with pytest.raises(ValueError):
            validate_port(0)

    def test_invalid_port_negative(self):
        """Test negative port (invalid)."""
        with pytest.raises(ValueError):
            validate_port(-1)

    def test_invalid_port_too_high(self):
        """Test port above 65535 (invalid)."""
        with pytest.raises(ValueError):
            validate_port(65536)

    def test_invalid_port_string_non_numeric(self):
        """Test non-numeric string port."""
        with pytest.raises(ValueError):
            validate_port("abc")


class TestValidateScanInterval:
    """Test suite for validate_scan_interval function."""

    def test_valid_interval_minimum(self):
        """Test minimum valid interval (10s)."""
        assert validate_scan_interval(10) == 10

    def test_valid_interval_maximum(self):
        """Test maximum valid interval (300s)."""
        assert validate_scan_interval(300) == 300

    def test_valid_interval_default(self):
        """Test default interval (30s)."""
        assert validate_scan_interval(30) == 30

    def test_valid_interval_string(self):
        """Test string conversion."""
        assert validate_scan_interval("60") == 60

    def test_invalid_interval_too_low(self):
        """Test interval below 10s."""
        with pytest.raises(ValueError):
            validate_scan_interval(9)

    def test_invalid_interval_too_high(self):
        """Test interval above 300s."""
        with pytest.raises(ValueError):
            validate_scan_interval(301)

    def test_invalid_interval_negative(self):
        """Test negative interval."""
        with pytest.raises(ValueError):
            validate_scan_interval(-30)

    def test_invalid_interval_zero(self):
        """Test zero interval."""
        with pytest.raises(ValueError):
            validate_scan_interval(0)


class TestValidateRebootInterval:
    """Test suite for validate_reboot_interval function."""

    def test_valid_interval_zero_disabled(self):
        """Test zero interval (reboot disabled)."""
        assert validate_reboot_interval(0) == 0

    def test_valid_interval_minimum_enabled(self):
        """Test minimum enabled interval (1 day)."""
        assert validate_reboot_interval(1) == 1

    def test_valid_interval_maximum(self):
        """Test maximum interval (30 days)."""
        assert validate_reboot_interval(30) == 30

    def test_valid_interval_default(self):
        """Test default interval (7 days)."""
        assert validate_reboot_interval(7) == 7

    def test_valid_interval_string(self):
        """Test string conversion."""
        assert validate_reboot_interval("14") == 14

    def test_invalid_interval_negative(self):
        """Test negative interval."""
        with pytest.raises(ValueError):
            validate_reboot_interval(-1)

    def test_invalid_interval_too_high(self):
        """Test interval above 30 days."""
        with pytest.raises(ValueError):
            validate_reboot_interval(31)


class TestValidateRebootTime:
    """Test suite for validate_reboot_time function."""

    def test_valid_time_midnight(self):
        """Test midnight (00:00)."""
        assert validate_reboot_time("00:00") == "00:00"

    def test_valid_time_noon(self):
        """Test noon (12:00)."""
        assert validate_reboot_time("12:00") == "12:00"

    def test_valid_time_end_of_day(self):
        """Test end of day (23:59)."""
        assert validate_reboot_time("23:59") == "23:59"

    def test_valid_time_default(self):
        """Test default time (03:00)."""
        assert validate_reboot_time("03:00") == "03:00"

    def test_valid_time_single_digit_hour(self):
        """Test single-digit hour (05:30)."""
        assert validate_reboot_time("05:30") == "05:30"

    def test_invalid_time_no_separator(self):
        """Test time without colon."""
        with pytest.raises(ValueError):
            validate_reboot_time("0300")

    def test_invalid_time_hour_too_high(self):
        """Test invalid hour (24:00)."""
        with pytest.raises(ValueError):
            validate_reboot_time("24:00")

    def test_invalid_time_minute_too_high(self):
        """Test invalid minute (12:60)."""
        with pytest.raises(ValueError):
            validate_reboot_time("12:60")

    def test_invalid_time_format_three_digits(self):
        """Test wrong format (HHH:MM)."""
        with pytest.raises(ValueError):
            validate_reboot_time("100:00")

    def test_invalid_time_empty(self):
        """Test empty string."""
        with pytest.raises(ValueError):
            validate_reboot_time("")

    def test_invalid_time_non_numeric(self):
        """Test non-numeric format."""
        with pytest.raises(ValueError):
            validate_reboot_time("AB:CD")


class TestValidateTempRefreshInterval:
    """Test suite for validate_temp_refresh_interval function."""

    def test_valid_interval_minimum(self):
        """Test minimum interval (1s)."""
        assert validate_temp_refresh_interval(1) == 1

    def test_valid_interval_maximum(self):
        """Test maximum interval (5s)."""
        assert validate_temp_refresh_interval(5) == 5

    def test_valid_interval_default(self):
        """Test default interval (2s)."""
        assert validate_temp_refresh_interval(2) == 2

    def test_valid_interval_string(self):
        """Test string conversion."""
        assert validate_temp_refresh_interval("3") == 3

    def test_invalid_interval_too_low(self):
        """Test interval below 1s."""
        with pytest.raises(ValueError):
            validate_temp_refresh_interval(0)

    def test_invalid_interval_too_high(self):
        """Test interval above 5s."""
        with pytest.raises(ValueError):
            validate_temp_refresh_interval(6)

    def test_invalid_interval_negative(self):
        """Test negative interval."""
        with pytest.raises(ValueError):
            validate_temp_refresh_interval(-1)


class TestValidateTempRefreshDuration:
    """Test suite for validate_temp_refresh_duration function."""

    def test_valid_duration_minimum(self):
        """Test minimum duration (30s)."""
        assert validate_temp_refresh_duration(30) == 30

    def test_valid_duration_maximum(self):
        """Test maximum duration (120s)."""
        assert validate_temp_refresh_duration(120) == 120

    def test_valid_duration_default(self):
        """Test default duration (120s)."""
        assert validate_temp_refresh_duration(120) == 120

    def test_valid_duration_string(self):
        """Test string conversion."""
        assert validate_temp_refresh_duration("60") == 60

    def test_invalid_duration_too_low(self):
        """Test duration below 30s."""
        with pytest.raises(ValueError):
            validate_temp_refresh_duration(29)

    def test_invalid_duration_too_high(self):
        """Test duration above 120s."""
        with pytest.raises(ValueError):
            validate_temp_refresh_duration(121)

    def test_invalid_duration_negative(self):
        """Test negative duration."""
        with pytest.raises(ValueError):
            validate_temp_refresh_duration(-30)


class TestValidateHost:
    """Test suite for validate_host function."""

    def test_valid_hostname(self):
        """Test valid hostname."""
        assert validate_host("freebox.local") == "freebox.local"

    def test_valid_hostname_with_underscore(self):
        """Test hostname with underscore."""
        assert validate_host("my_freebox") == "my_freebox"

    def test_valid_ipv4_address(self):
        """Test valid IPv4 address."""
        assert validate_host("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_loopback(self):
        """Test localhost IPv4."""
        assert validate_host("127.0.0.1") == "127.0.0.1"

    def test_valid_hostname_long(self):
        """Test long hostname."""
        host = "very-long-freebox-hostname-example.local"
        assert validate_host(host) == host

    def test_invalid_host_empty(self):
        """Test empty string."""
        with pytest.raises(ValueError):
            validate_host("")

    def test_invalid_host_too_long(self):
        """Test hostname exceeding maximum length (255 chars)."""
        long_host = "a" * 256
        with pytest.raises(ValueError):
            validate_host(long_host)


class TestGetValidationBounds:
    """Test suite for get_validation_bounds function."""

    def test_bounds_structure(self):
        """Test that bounds dict has correct structure."""
        bounds = get_validation_bounds()
        assert isinstance(bounds, dict)
        assert len(bounds) > 0

    def test_bounds_keys(self):
        """Test that all expected keys are present."""
        bounds = get_validation_bounds()
        expected_keys = [
            "port",
            "scan_interval",
            "reboot_interval",
            "reboot_time",
            "temp_refresh_interval",
            "temp_refresh_duration",
        ]
        for key in expected_keys:
            assert key in bounds

    def test_bounds_port_values(self):
        """Test port bounds values."""
        bounds = get_validation_bounds()
        port_bounds = bounds["port"]
        assert port_bounds["min"] == 1
        assert port_bounds["max"] == 65535
        assert port_bounds["unit"] == "port"

    def test_bounds_scan_interval_values(self):
        """Test scan interval bounds values."""
        bounds = get_validation_bounds()
        interval_bounds = bounds["scan_interval"]
        assert interval_bounds["min"] == 10
        assert interval_bounds["max"] == 300
        assert interval_bounds["unit"] == "seconds"

    def test_bounds_reboot_interval_values(self):
        """Test reboot interval bounds values."""
        bounds = get_validation_bounds()
        reboot_bounds = bounds["reboot_interval"]
        assert reboot_bounds["min"] == 0
        assert reboot_bounds["max"] == 30
        assert reboot_bounds["unit"] == "days"


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_port_boundary_values(self):
        """Test all port boundary values."""
        # Valid boundaries
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535

        # Invalid boundaries
        with pytest.raises(ValueError):
            validate_port(0)
        with pytest.raises(ValueError):
            validate_port(65536)

    def test_time_boundary_values(self):
        """Test all time boundary values."""
        # Valid boundaries
        assert validate_reboot_time("00:00") == "00:00"
        assert validate_reboot_time("23:59") == "23:59"

        # Invalid boundaries
        with pytest.raises(ValueError):
            validate_reboot_time("24:00")
        with pytest.raises(ValueError):
            validate_reboot_time("23:60")

    def test_all_valid_hours(self):
        """Test all valid hours (0-23)."""
        for hour in range(24):
            time_str = f"{hour:02d}:00"
            assert validate_reboot_time(time_str) == time_str

    def test_all_valid_minutes(self):
        """Test all valid minutes (0-59)."""
        for minute in range(0, 60, 5):  # Test every 5 minutes
            time_str = f"12:{minute:02d}"
            assert validate_reboot_time(time_str) == time_str

    def test_type_conversion_strings(self):
        """Test automatic type conversion from strings."""
        assert validate_port("443") == 443
        assert validate_scan_interval("30") == 30
        assert validate_reboot_interval("7") == 7


class TestErrorMessages:
    """Test suite for validation error messages."""

    def test_port_error_message(self):
        """Test port validation error message."""
        try:
            validate_port(99999)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "port" in str(e).lower()
            assert "1" in str(e)
            assert "65535" in str(e)

    def test_interval_error_message(self):
        """Test interval validation error message."""
        try:
            validate_scan_interval(500)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "scan" in str(e).lower() or "interval" in str(e).lower()

    def test_time_error_message(self):
        """Test time validation error message."""
        try:
            validate_reboot_time("25:00")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "time" in str(e).lower() or "format" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
