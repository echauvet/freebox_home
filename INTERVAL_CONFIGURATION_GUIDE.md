# Interval Configuration Guide

## Overview

Freebox Home uses two polling strategies to balance responsiveness with API efficiency:

1. **Normal Polling**: Regular updates at configurable intervals (default 30 seconds)
2. **Fast Polling**: Temporary rapid updates after cover commands (default 2 seconds for 120 seconds)

This guide explains how to configure these intervals for optimal performance.

---

## Normal Polling Intervals

### Concept
The normal polling interval determines how often the integration checks the Freebox API for updates to devices, sensors, and home automation status.

### Configuration Range
- **Minimum**: 10 seconds
- **Default**: 30 seconds
- **Maximum**: 300 seconds

### Effects by Interval

| Interval | API Calls/Hour | Use Case | Trade-offs |
|----------|-----------------|----------|-----------|
| 10 seconds | 360 | Live monitoring, frequent state changes | Higher API load, more responsive |
| 20 seconds | 180 | Balanced monitoring | Moderate load, good responsiveness |
| 30 seconds | 120 | **DEFAULT** - recommended for most users | Efficient, good responsiveness |
| 60 seconds | 60 | Conservative, battery-conscious | Lower load, slightly delayed updates |
| 300 seconds | 12 | Minimal API usage | Very delayed updates, minimal load |

### Recommendations

**Use LOW intervals (10-20s) if:**
- You have frequent cover movements
- You want real-time sensor updates
- Your Freebox supports high API throughput
- You're not API-rate-limited

**Use DEFAULT (30s) if:**
- You want a balanced approach (most users)
- You have moderate cover activity
- You want efficient API usage without sacrificing responsiveness

**Use HIGH intervals (60-300s) if:**
- You want minimal API usage
- You have limited API rate limits
- Cover movements are infrequent
- You can tolerate slower state updates

---

## Fast Polling: Interval & Duration

### Concept
When you command a cover to move (open/close/set position), the integration activates "fast polling" to show real-time progress in Home Assistant's UI. This provides immediate feedback instead of waiting for the next normal poll.

### Configuration Range

#### Fast Polling Interval (1-5 seconds)
How frequently to check the API during fast polling.

| Interval | API Calls/Minute | Responsiveness | Best For |
|----------|------------------|-----------------|----------|
| 1 second | 60 | Very fast, immediate | Position tracking, urgent feedback |
| 2 seconds | 30 | **DEFAULT** - balanced | Standard cover operations |
| 3 seconds | 20 | Good responsiveness | Conservative approach |
| 5 seconds | 12 | Minimal extra load | API-limited scenarios |

**Default**: 2 seconds
**Use Case**: Provides smooth real-time position updates without excessive API calls

#### Fast Polling Duration (30-120 seconds)
How long to maintain fast polling after a command.

| Duration | Scenario | API Calls per Movement | Notes |
|----------|----------|----------------------|-------|
| 30 seconds | Quick checks | 15-30 API calls | Stop monitoring quickly |
| 60 seconds | Standard operations | 30-60 API calls | **DEFAULT** - covers most movements |
| 90 seconds | Slow covers | 45-90 API calls | Extended feedback window |
| 120 seconds | Very slow covers | 60-120 API calls | Maximum feedback period |

**Default**: 120 seconds
**Calculation**: `API calls during movement = (movement_duration / polling_interval) + (remaining_duration / polling_interval)`

### API Load Calculation

**Example 1: Standard fast polling (2s interval, 120s duration)**
```
Cover moves for 15 seconds:
- During movement: 15 ÷ 2 = 8 API calls
- After movement: remaining 105 seconds ÷ 2 = 53 API calls
- Total: ~60 API calls per cover movement
```

**Example 2: Fast interval (1s interval, 120s duration)**
```
- During movement: 15 ÷ 1 = 15 API calls
- After movement: 105 ÷ 1 = 105 API calls
- Total: ~120 API calls per cover movement (2x more!)
```

**Example 3: Conservative interval (5s interval, 60s duration)**
```
- During movement: 15 ÷ 5 = 3 API calls
- After movement: 45 ÷ 5 = 9 API calls
- Total: ~12 API calls per cover movement (5x fewer!)
```

### Optimization Examples

#### Responsive Configuration
For fast UI feedback with moderate API usage:
- Normal Polling Interval: 30 seconds
- Fast Polling Interval: 1-2 seconds
- Fast Polling Duration: 120 seconds

**API Load**: ~60-120 calls per cover movement + normal polling

#### Conservative Configuration
For minimal API usage:
- Normal Polling Interval: 60 seconds
- Fast Polling Interval: 3-5 seconds
- Fast Polling Duration: 60 seconds

**API Load**: ~12-20 calls per cover movement + minimal polling

#### Balanced Configuration (DEFAULT)
Recommended for most users:
- Normal Polling Interval: 30 seconds
- Fast Polling Interval: 2 seconds
- Fast Polling Duration: 120 seconds

**API Load**: ~60 calls per cover movement + balanced polling

---

## Caching Interaction with Intervals

### How Caching Works
The integration caches device and sensor data with a 120-second TTL (Time To Live). This means:

- During fast polling (2s interval): Most updates served from cache
- During normal polling (30s interval): Cache hits most of the time
- Overall API reduction: **40-94%** depending on interval configuration

### Caching Benefits by Interval

#### Normal Polling (30s)
```
4 normal polls = 120 seconds = 1 cache cycle
Cache hit rate: ~75%
Actual API calls: 25% of requested updates
Effect: 40% reduction in API calls
```

#### Fast Polling (2s)
```
60 fast polls = 120 seconds = 1 cache cycle
Cache hit rate: ~94%
Actual API calls: 6% of requested updates
Effect: 94% reduction during fast polling!
```

#### Fast Polling (1s)
```
120 fast polls = 120 seconds = 1 cache cycle
Cache hit rate: ~99%
Actual API calls: 1% of requested updates
Effect: 99% reduction (max efficiency!)
```

### Daily Impact

**Scenario: 5 cover movements per day, 15 seconds each**

With 2-second fast polling + 30-second normal polling:
- Fast polling calls: 5 × 60 = 300 calls
- Normal polling (86,400 seconds/day): ~720 calls
- Without caching: ~1,020 calls/day
- **With caching: ~60-120 calls/day (94% reduction!)**

---

## Advanced Configuration

### API Rate Limiting
If you hit Freebox API rate limits:

1. **Increase normal polling interval**
   ```
   Normal interval: 30s → 60s (halves API calls)
   Effect: Slightly delayed state updates
   ```

2. **Increase fast polling interval**
   ```
   Fast interval: 2s → 3-5s (reduces feedback speed)
   Effect: Less smooth real-time updates
   ```

3. **Reduce fast polling duration**
   ```
   Duration: 120s → 60s (stops fast polling earlier)
   Effect: Less feedback after cover stops
   ```

### Balancing Responsiveness vs Efficiency

**Maximum Responsiveness**
- Normal: 10-15 seconds
- Fast: 1 second
- Duration: 120 seconds
- API Load: Very high (~500+ calls/hour during activity)

**Balanced (Recommended)**
- Normal: 30 seconds (default)
- Fast: 2 seconds (default)
- Duration: 120 seconds (default)
- API Load: Moderate (~120 calls/hour baseline + 60 per movement)

**Maximum Efficiency**
- Normal: 60-120 seconds
- Fast: 5 seconds
- Duration: 60 seconds
- API Load: Low (~30 calls/hour baseline + 12 per movement)

---

## Troubleshooting

### Slow Cover State Updates
**Symptom**: Cover position updates slowly in Home Assistant UI

**Solutions**:
1. Reduce fast polling interval (1-2 seconds)
2. Increase fast polling duration (120 seconds)
3. Reduce normal polling interval (20-30 seconds)

### High API Usage / Rate Limiting
**Symptom**: Getting throttled by Freebox API

**Solutions**:
1. Increase normal polling interval (60+ seconds)
2. Increase fast polling interval (3-5 seconds)
3. Reduce fast polling duration (30-60 seconds)
4. Monitor `CODE_QUALITY_REPORT.md` for performance metrics

### Inconsistent Entity States
**Symptom**: Entity states are inconsistent or delayed

**Solutions**:
1. Verify normal polling interval is reasonable (10-60 seconds)
2. Check Freebox API availability
3. Review Home Assistant logs for errors
4. Restart the integration

---

## Performance Metrics

Default configuration performance:

| Metric | Value |
|--------|-------|
| Normal polling API calls | ~120/hour baseline |
| Fast polling API reduction | 94% (with caching) |
| Cache hit rate (normal poll) | ~75% |
| Cache hit rate (fast poll) | ~94% |
| Cached operation speed | 94% faster (10ms vs 161ms) |
| Startup time improvement | 14% faster |

---

## Examples

### Example 1: Smart Home with Frequent Movement
**Goal**: Responsive cover feedback, moderate API usage

**Configuration**:
```
Normal Polling Interval: 20 seconds
Fast Polling Interval: 1 second
Fast Polling Duration: 120 seconds
```

**Benefits**:
- Very responsive real-time updates (1s feedback)
- Frequent state checks (20s normal poll)
- Acceptable API usage with caching

### Example 2: Battery-Conscious Setup
**Goal**: Minimal API usage, battery efficiency

**Configuration**:
```
Normal Polling Interval: 120 seconds
Fast Polling Interval: 5 seconds
Fast Polling Duration: 30 seconds
```

**Benefits**:
- Minimal API calls (~15 calls/hour baseline)
- Very low battery impact
- Reduced load on Freebox

### Example 3: Heavy Activity Environment
**Goal**: Multiple covers, frequent movements, responsive feedback

**Configuration**:
```
Normal Polling Interval: 30 seconds (default)
Fast Polling Interval: 2 seconds (default)
Fast Polling Duration: 120 seconds (default)
```

**Benefits**:
- Smooth real-time feedback (2s updates)
- Efficient caching (94% reduction during fast poll)
- Balanced API usage
- **Recommended for most users**

---

## Related Documentation

- See `const.py` for configuration constants and validation ranges
- See `validation.py` for interval validator functions
- See `cover.py` for implementation details of fast polling
- See `router.py` for caching implementation
- See `CODE_QUALITY_REPORT.md` for performance metrics

---

## Summary

| Setting | Low | Default | High |
|---------|-----|---------|------|
| Normal Polling | 10-20s | 30s | 60-300s |
| Fast Polling Interval | 1s | 2s | 3-5s |
| Fast Polling Duration | 30s | 120s | 120s |
| Responsiveness | Maximum | Balanced | Minimal |
| API Load | High | Moderate | Low |
| Recommended For | Live monitoring | Most users | Battery/efficiency |
