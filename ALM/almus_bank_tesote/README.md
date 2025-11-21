# Bank Tesote Integration

Integration with Tesote API v2 for automatic bank statement import.

Developed by Almus Dev (JDV-ALM) - www.almus.dev

## Features

### API Rate Limiting
- **Automatic rate limiting**: Maximum of 190 requests per minute (safety margin from the 200 limit)
- **Smart distribution**: Requests are evenly distributed throughout the minute to avoid bursts
- **Automatic waiting**: System automatically waits when rate limit is approached

### Retry Logic
- **Automatic retries**: Up to 3 retry attempts for failed requests
- **Exponential backoff**: Progressive wait times (2, 4, 8 seconds) between retries
- **Smart retry handling**:
  - Network timeouts: Automatic retry with backoff
  - Connection errors: Automatic retry with backoff
  - Rate limit errors (429): Extended backoff (10, 20, 40 seconds)
  - Server errors (500, 502, 503, 504): Automatic retry with backoff
  - Authentication errors (401): No retry, immediate user notification
  
### Enhanced Error Handling
- Clear error messages for each failure type
- Detailed logging for troubleshooting
- Graceful degradation (returns partial results when possible)

## Configuration

### Settings
1. Go to **Settings > Accounting**
2. Find **Tesote Integration** section
3. Configure:
   - **API Key**: Your Tesote API key
   - **Days to Sync**: Number of days for automatic sync (default: 7)
   - **Automatic Sync**: Enable/disable scheduled synchronization

### Test Connection
Use the **Test Connection** button in settings to verify your API configuration.

### Fetch Accounts
Click **Fetch Accounts** to retrieve available bank accounts from Tesote.

## Usage

### Manual Synchronization
1. Go to **Accounting > Configuration > Journals**
2. Select a bank journal
3. Configure:
   - **Tesote Account**: Select the corresponding Tesote account
   - **Enable Tesote Sync**: Enable for automatic synchronization
4. Click **Sync from Tesote** button

### Wizard Synchronization
1. Go to **Accounting > Tesote > Sync from Tesote**
2. Select journals to sync
3. Choose date range
4. Click **Sync**

### Automatic Synchronization
When enabled in settings, the system will automatically sync all enabled journals daily.

## Technical Details

### Rate Limiting Implementation
```python
class RateLimiter (Singleton):
    - Single shared instance across all API calls
    - Thread-safe with locking mechanism
    - Tracks request timestamps globally
    - Removes old requests outside time window
    - Calculates wait time when limit reached
    - Distributes requests evenly with minimum interval
```

**Benefits of Singleton Pattern:**
- Ensures rate limit applies globally across all Odoo workers and API instances
- Prevents multiple rate limiter instances from conflicting
- Thread-safe implementation for concurrent requests
- More accurate rate limiting in multi-threaded environments

### Retry Strategy
- **Timeout errors**: 3 retries with 2^n second backoff
- **Connection errors**: 3 retries with 2^n second backoff
- **Rate limit (429)**: 3 retries with extended backoff (2^n * 5 seconds)
- **Server errors (5xx)**: 3 retries with 2^n second backoff
- **Client errors (4xx, except 429)**: No retry

### Performance Optimizations
- **Pagination**: Automatic handling of paginated responses
- **Batch processing**: Fetches 50-100 items per request
- **Duplicate prevention**: Checks existing transactions before import
- **Safe limits**: Maximum iterations to prevent infinite loops

## API Endpoints Used

- `/status` - Connection test and authentication
- `/accounts` - Fetch available bank accounts (paginated)
- `/accounts/{id}/transactions` - Fetch account transactions (paginated with cursor)

## Error Handling

### Common Issues

**"Rate limit exceeded"**
- System will automatically retry after waiting
- Manual sync: Wait a few minutes and try again
- Reduce date range for large syncs

**"Timeout errors"**
- System will retry automatically (up to 3 times)
- Check internet connection
- Try during off-peak hours

**"Invalid API key"**
- Verify API key in Settings > Accounting
- Contact Tesote support if key is correct

**"Transaction fetch exceeded maximum pages"**
- Use smaller date ranges
- Contact support if issue persists

## Best Practices

1. **Date Ranges**: Use smaller date ranges (1-30 days) for better performance
2. **Peak Hours**: Avoid syncing during peak banking hours if possible
3. **Monitoring**: Check logs regularly for any sync issues
4. **Testing**: Test with a single journal before enabling multiple journals

## Logging

All API operations are logged with appropriate levels:
- **INFO**: Successful operations, pagination progress
- **WARNING**: Non-critical issues, approaching limits
- **ERROR**: Failed operations, critical issues

Check Odoo logs for detailed information:
```
grep "tesote" odoo.log
```

## Dependencies

- Python `requests` library
- Odoo modules:
  - `account`
  - `account_accountant`
  - `account_bank_statement_import`

## Support

For issues or questions:
- Website: https://www.almus.dev
- Check logs for detailed error messages
- Verify API key and Tesote account status

## Version History

### 1.0.0
- Initial release with basic synchronization
- Rate limiting (max 190 requests/minute)
- Automatic retry logic (up to 3 attempts)
- Exponential backoff strategy
- Enhanced error handling and logging