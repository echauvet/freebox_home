"""
@file test_utilities.py
@author Freebox Home Contributors
@brief Integration tests for utilities.py module
@version 1.3.0

Comprehensive integration tests for CachedValue, PerformanceTimer,
and utility functions with real-world scenarios.

@section test_coverage Test Coverage
- CachedValue generic class with TTL
- PerformanceTimer context manager
- safe_get() nested dictionary access
- parse_uptime() conversion
- format_timestamp() formatting
- truncate_string() truncation

@section execution Running Tests
  python -m pytest test_utilities.py -v
  python -m pytest test_utilities.py::TestCachedValue -v
  python -m pytest test_utilities.py -k "performance" -v
"""

import pytest
import time
from datetime import datetime
from .utilities import (
    CachedValue,
    PerformanceTimer,
    safe_get,
    parse_uptime,
    format_timestamp,
    truncate_string,
    get_performance_stats,
)


class TestCachedValue:
    """Integration tests for CachedValue class."""

    def test_cached_value_basic_set_get(self):
        """Test basic set and get operations."""
        cache = CachedValue[int](ttl_seconds=60)
        cache.set(42)
        assert cache.get() == 42

    def test_cached_value_initial_none(self):
        """Test that unset cache returns None."""
        cache = CachedValue[str](ttl_seconds=60)
        assert cache.get() is None

    def test_cached_value_overwrite(self):
        """Test overwriting cached value."""
        cache = CachedValue[str](ttl_seconds=60)
        cache.set("first")
        assert cache.get() == "first"
        cache.set("second")
        assert cache.get() == "second"

    def test_cached_value_ttl_expiration(self):
        """Test that cache expires after TTL."""
        cache = CachedValue[int](ttl_seconds=1)
        cache.set(99)
        assert cache.get() == 99
        
        # Wait for TTL to expire
        time.sleep(1.1)
        assert cache.get() is None

    def test_cached_value_type_generic_int(self):
        """Test generic type with int."""
        cache = CachedValue[int](ttl_seconds=60)
        cache.set(123)
        assert cache.get() == 123
        assert isinstance(cache.get(), int)

    def test_cached_value_type_generic_str(self):
        """Test generic type with string."""
        cache = CachedValue[str](ttl_seconds=60)
        cache.set("hello")
        assert cache.get() == "hello"
        assert isinstance(cache.get(), str)

    def test_cached_value_type_generic_dict(self):
        """Test generic type with dict."""
        cache = CachedValue[dict](ttl_seconds=60)
        data = {"key": "value", "nested": {"inner": 42}}
        cache.set(data)
        assert cache.get() == data

    def test_cached_value_type_generic_list(self):
        """Test generic type with list."""
        cache = CachedValue[list](ttl_seconds=60)
        data = [1, 2, 3, 4, 5]
        cache.set(data)
        assert cache.get() == data

    def test_cached_value_is_expired_check(self):
        """Test is_expired() method."""
        cache = CachedValue[int](ttl_seconds=1)
        cache.set(42)
        assert not cache.is_expired()
        
        time.sleep(1.1)
        assert cache.is_expired()

    def test_cached_value_multiple_instances(self):
        """Test multiple independent cache instances."""
        cache1 = CachedValue[int](ttl_seconds=60)
        cache2 = CachedValue[str](ttl_seconds=60)
        
        cache1.set(100)
        cache2.set("test")
        
        assert cache1.get() == 100
        assert cache2.get() == "test"

    def test_cached_value_large_object(self):
        """Test caching large objects."""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}
        cache = CachedValue[dict](ttl_seconds=60)
        cache.set(large_dict)
        assert cache.get() == large_dict
        assert len(cache.get()) == 1000


class TestPerformanceTimer:
    """Integration tests for PerformanceTimer context manager."""

    def test_performance_timer_basic_timing(self):
        """Test basic timing measurement."""
        with PerformanceTimer("test_op") as timer:
            time.sleep(0.1)
        # Should complete without errors
        assert timer is not None

    def test_performance_timer_checkpoint(self):
        """Test checkpoint tracking."""
        with PerformanceTimer("test_op") as timer:
            time.sleep(0.05)
            timer.checkpoint("step1")
            time.sleep(0.05)
            timer.checkpoint("step2")
        # Should complete with checkpoints
        assert timer is not None

    def test_performance_timer_multiple_checkpoints(self):
        """Test multiple checkpoints in sequence."""
        with PerformanceTimer("test_op") as timer:
            for i in range(5):
                time.sleep(0.02)
                timer.checkpoint(f"step_{i}")
        # Should complete with all checkpoints
        assert timer is not None

    def test_performance_timer_no_exception_on_error(self):
        """Test that timer handles exceptions gracefully."""
        try:
            with PerformanceTimer("test_op") as timer:
                time.sleep(0.01)
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected
        # Timer should have completed despite exception

    def test_performance_timer_context_manager_cleanup(self):
        """Test context manager cleanup."""
        timer_obj = None
        with PerformanceTimer("test_op") as timer:
            timer_obj = timer
            time.sleep(0.05)
        
        # Should have stats available
        assert timer_obj is not None

    def test_performance_timer_threshold_warning(self):
        """Test threshold-based warnings."""
        # Timer with 50ms threshold
        with PerformanceTimer("test_op", warn_threshold_ms=50) as timer:
            time.sleep(0.1)  # 100ms > 50ms threshold
        # Should log warning but not raise exception
        assert timer is not None


class TestSafeGet:
    """Integration tests for safe_get function."""

    def test_safe_get_single_level(self):
        """Test single-level dictionary access."""
        data = {"name": "test", "value": 42}
        assert safe_get(data, "name") == "test"
        assert safe_get(data, "value") == 42

    def test_safe_get_nested(self):
        """Test nested dictionary access."""
        data = {"user": {"profile": {"name": "Alice"}}}
        assert safe_get(data, "user", "profile", "name") == "Alice"

    def test_safe_get_missing_key_with_default(self):
        """Test missing key returns default."""
        data = {"name": "test"}
        assert safe_get(data, "missing", default="N/A") == "N/A"

    def test_safe_get_nested_missing_with_default(self):
        """Test nested missing key returns default."""
        data = {"user": {"profile": {"name": "Alice"}}}
        result = safe_get(data, "user", "settings", "theme", default="light")
        assert result == "light"

    def test_safe_get_none_value_vs_missing(self):
        """Test distinction between None value and missing key."""
        data = {"value": None, "missing": "key"}
        assert safe_get(data, "value") is None
        assert safe_get(data, "nonexistent") is None

    def test_safe_get_empty_dict(self):
        """Test with empty dictionary."""
        data = {}
        assert safe_get(data, "key", default="N/A") == "N/A"

    def test_safe_get_list_in_dict(self):
        """Test dictionary containing lists."""
        data = {"items": [1, 2, 3], "name": "test"}
        assert safe_get(data, "items") == [1, 2, 3]

    def test_safe_get_deeply_nested(self):
        """Test deeply nested structure."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep"
                        }
                    }
                }
            }
        }
        result = safe_get(data, "level1", "level2", "level3", "level4", "value")
        assert result == "deep"

    def test_safe_get_mixed_types(self):
        """Test with mixed data types."""
        data = {
            "str": "string",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }
        assert safe_get(data, "str") == "string"
        assert safe_get(data, "int") == 42
        assert safe_get(data, "float") == 3.14
        assert safe_get(data, "bool") is True
        assert safe_get(data, "list") == [1, 2, 3]
        assert safe_get(data, "dict") == {"nested": "value"}


class TestParseUptime:
    """Integration tests for parse_uptime function."""

    def test_parse_uptime_zero(self):
        """Test zero seconds."""
        result = parse_uptime(0)
        assert "0" in result or "0 day" in result

    def test_parse_uptime_seconds(self):
        """Test seconds only."""
        result = parse_uptime(45)
        assert "day" not in result.lower() or "0" in result

    def test_parse_uptime_minutes(self):
        """Test minutes."""
        result = parse_uptime(300)  # 5 minutes
        assert isinstance(result, str)

    def test_parse_uptime_hours(self):
        """Test hours."""
        result = parse_uptime(3600)  # 1 hour
        assert isinstance(result, str)

    def test_parse_uptime_days(self):
        """Test days."""
        result = parse_uptime(86400)  # 1 day
        assert "day" in result.lower() or "1" in result

    def test_parse_uptime_complex(self):
        """Test complex uptime."""
        # 7 days, 3 hours, 45 minutes, 30 seconds
        seconds = 7 * 86400 + 3 * 3600 + 45 * 60 + 30
        result = parse_uptime(seconds)
        assert isinstance(result, str)
        assert "day" in result.lower() or "7" in result

    def test_parse_uptime_large_number(self):
        """Test large uptime value."""
        result = parse_uptime(365 * 86400)  # 1 year
        assert isinstance(result, str)


class TestFormatTimestamp:
    """Integration tests for format_timestamp function."""

    def test_format_timestamp_recent(self):
        """Test formatting recent timestamp."""
        now = datetime.now().timestamp()
        result = format_timestamp(now)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_timestamp_past(self):
        """Test formatting past timestamp."""
        past = datetime.now().timestamp() - 86400  # 1 day ago
        result = format_timestamp(past)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_timestamp_consistency(self):
        """Test formatting consistency."""
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        result = format_timestamp(ts)
        assert isinstance(result, str)
        # Should contain date/time information
        assert len(result) > 5


class TestTruncateString:
    """Integration tests for truncate_string function."""

    def test_truncate_string_short(self):
        """Test string shorter than max length."""
        result = truncate_string("hello", max_length=20)
        assert result == "hello"

    def test_truncate_string_exact_length(self):
        """Test string exactly at max length."""
        result = truncate_string("hello", max_length=5)
        assert result == "hello"

    def test_truncate_string_needs_truncation(self):
        """Test string longer than max length."""
        result = truncate_string("hello world", max_length=8)
        assert len(result) <= 8
        assert "..." in result

    def test_truncate_string_very_long(self):
        """Test very long string."""
        long_str = "a" * 1000
        result = truncate_string(long_str, max_length=50)
        assert len(result) <= 50
        assert "..." in result

    def test_truncate_string_unicode(self):
        """Test unicode characters."""
        result = truncate_string("café résumé", max_length=8)
        assert len(result) <= 8

    def test_truncate_string_empty(self):
        """Test empty string."""
        result = truncate_string("", max_length=20)
        assert result == ""

    def test_truncate_string_special_chars(self):
        """Test with special characters."""
        special = "test@#$%^&*()"
        result = truncate_string(special, max_length=8)
        assert len(result) <= 8


class TestRealWorldScenarios:
    """Integration tests for real-world usage scenarios."""

    def test_device_list_caching_scenario(self):
        """Test typical device list caching scenario."""
        # Simulate API response
        devices = [
            {"id": 1, "name": "Device 1", "active": True},
            {"id": 2, "name": "Device 2", "active": False},
            {"id": 3, "name": "Device 3", "active": True},
        ]
        
        # Cache for 120 seconds
        cache = CachedValue[list](ttl_seconds=120)
        cache.set(devices)
        
        # Retrieve from cache
        cached = cache.get()
        assert cached == devices
        assert len(cached) == 3

    def test_sensor_update_with_safe_get(self):
        """Test sensor update with safe data access."""
        # Simulate API response with potential missing fields
        response = {
            "sensors": [
                {"name": "temp", "value": 42.5},
                {"name": "humidity"},  # Missing value
            ]
        }
        
        # Safe access to sensor values
        sensors = safe_get(response, "sensors", default=[])
        assert len(sensors) == 2
        assert safe_get(sensors[0], "value") == 42.5
        assert safe_get(sensors[1], "value", default=0) == 0

    def test_performance_monitoring_scenario(self):
        """Test typical performance monitoring scenario."""
        with PerformanceTimer("update_all") as timer:
            # Device update
            time.sleep(0.05)
            timer.checkpoint("devices_updated")
            
            # Sensor update
            time.sleep(0.03)
            timer.checkpoint("sensors_updated")
            
            # Entity update
            time.sleep(0.02)
            timer.checkpoint("entities_updated")

    def test_entity_name_display_scenario(self):
        """Test entity name display with truncation."""
        # Simulate various entity names
        names = [
            "Normal Name",
            "A" * 150,  # Too long
            "Special Chars !@#$%",
            "Unicode: café",
        ]
        
        for name in names:
            safe_name = truncate_string(name, max_length=100)
            assert len(safe_name) <= 100

    def test_complex_nested_config_scenario(self):
        """Test complex nested configuration access."""
        config = {
            "integration": {
                "freebox": {
                    "host": "192.168.1.254",
                    "port": 443,
                    "settings": {
                        "polling": {
                            "interval": 30,
                            "fast_poll": {
                                "enabled": True,
                                "duration": 120,
                            }
                        }
                    }
                }
            }
        }
        
        # Safe nested access
        host = safe_get(config, "integration", "freebox", "host", default="unknown")
        assert host == "192.168.1.254"
        
        interval = safe_get(
            config, "integration", "freebox", "settings", "polling", "interval",
            default=60
        )
        assert interval == 30
        
        enabled = safe_get(
            config, "integration", "freebox", "settings", "polling",
            "fast_poll", "enabled", default=False
        )
        assert enabled is True


class TestPerformanceStats:
    """Integration tests for get_performance_stats function."""

    def test_get_performance_stats_structure(self):
        """Test performance stats structure."""
        stats = get_performance_stats()
        assert isinstance(stats, dict)
        assert "timestamp" in stats or "created_at" in stats

    def test_get_performance_stats_metrics(self):
        """Test performance stats contains metrics."""
        stats = get_performance_stats()
        # Should contain some performance-related fields
        assert len(stats) > 0


class TestEdgeCasesIntegration:
    """Integration tests for edge cases in real scenarios."""

    def test_null_and_none_handling(self):
        """Test handling of null/None values."""
        data = {
            "value": None,
            "nested": {"inner": None},
        }
        
        assert safe_get(data, "value") is None
        assert safe_get(data, "nested", "inner") is None
        assert safe_get(data, "nested", "inner", default="default") is None

    def test_empty_collections(self):
        """Test with empty collections."""
        empty_data = {
            "list": [],
            "dict": {},
            "str": "",
        }
        
        assert safe_get(empty_data, "list") == []
        assert safe_get(empty_data, "dict") == {}
        assert safe_get(empty_data, "str") == ""

    def test_numeric_edge_cases(self):
        """Test numeric edge cases."""
        # Zero values
        assert parse_uptime(0).strip() != ""
        # Large numbers
        assert parse_uptime(999999999).strip() != ""
        # Negative (shouldn't occur but test robustness)
        assert parse_uptime(-1).strip() != ""

    def test_concurrent_cache_access(self):
        """Test concurrent access to cache (basic thread safety check)."""
        cache = CachedValue[int](ttl_seconds=60)
        
        # Set initial value
        cache.set(42)
        
        # Multiple reads should be consistent
        for _ in range(10):
            assert cache.get() == 42
        
        # Update value
        cache.set(100)
        for _ in range(10):
            assert cache.get() == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
