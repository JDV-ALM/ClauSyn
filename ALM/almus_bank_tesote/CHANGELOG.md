# Changelog

All notable changes to the Bank Tesote Integration module will be documented in this file.

## [1.1.0] - 2024-11-04

### Added
- **Rate Limiting System (Singleton Pattern)**
  - Automatic rate limiting to respect API limits (max 200 requests/minute)
  - Smart request distribution with minimum interval between requests (0.3 seconds)
  - Safety margin set to 190 requests/minute to avoid hitting limits
  - Request time tracking using deque for efficient cleanup
  - **Singleton implementation**: Single shared instance across all API calls
  - **Thread-safe**: Uses threading locks for concurrent request handling
  - **Global enforcement**: Rate limit applies across all Odoo workers
  
- **Retry Logic**
  - Automatic retry for transient failures (up to 3 attempts)
  - Exponential backoff strategy:
    - Timeout/Connection errors: 2, 4, 8 seconds
    - Rate limit errors (429): 10, 20, 40 seconds (extended backoff)
    - Server errors (5xx): 2, 4, 8 seconds
  - Support for Retry-After header from API responses
  
- **Enhanced Error Handling**
  - Specific error messages for each failure type
  - Better logging with context information
  - Graceful degradation (returns partial results when possible)
  - Detailed retry attempt logging
  
- **Performance Improvements**
  - Increased max_pages limit to 100 (from 10) due to rate limiting safety
  - Increased max_iterations to 100 (from 50) for transaction pagination
  - Better handling of large data sets

### Changed
- `_make_request()` method now includes retry logic and rate limiting
- All API methods (`get_accounts`, `get_transactions`, `test_connection`) benefit from automatic retries
- Improved logging throughout the module with more context
- Version bumped to 1.1.0

### Fixed
- Prevents API rate limit errors by proactive rate limiting
- Handles temporary network issues with automatic retries
- Better handling of server-side errors (5xx)
- More resilient transaction fetching for large date ranges

### Technical Details

#### RateLimiter Class (Singleton)
```python
class RateLimiter:
    def __new__(cls, max_requests=200, time_window=60)  # Singleton pattern
    def __init__(self, max_requests=200, time_window=60)
    def wait_if_needed()  # Thread-safe with lock
```
- **Singleton pattern**: Only one instance exists globally
- **Thread-safe**: Uses threading.Lock for concurrent access
- Tracks request timestamps in a sliding window
- Automatically waits when rate limit is approached
- Distributes requests evenly to prevent bursts
- Shared across all TesoteAPI instances

#### Retry Strategy
- **Retryable errors**: Timeout, Connection, 429, 500, 502, 503, 504
- **Non-retryable errors**: 401 (authentication), 4xx (client errors)
- **Max retries**: 3 attempts per request
- **Backoff**: Exponential with special handling for rate limits

#### Safety Features
- Maximum iteration limits to prevent infinite loops
- Request time tracking for accurate rate limiting
- Comprehensive error logging for troubleshooting
- Graceful handling of partial data retrieval

## [1.0.0] - Initial Release

### Added
- Basic Tesote API integration
- Account and transaction synchronization
- Manual and automatic sync options
- Configuration settings
- Wizard for selective synchronization
- Cron job for scheduled sync
- Duplicate transaction prevention