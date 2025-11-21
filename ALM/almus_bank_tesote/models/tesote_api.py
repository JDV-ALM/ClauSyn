# -*- coding: utf-8 -*-

import requests
import logging
import time
from datetime import datetime, timedelta
from odoo import models, api, _
from odoo.exceptions import UserError
from collections import deque

_logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter to ensure we don't exceed API rate limits (Singleton pattern)"""
    
    _instance = None
    _lock = None
    
    def __new__(cls, max_requests=200, time_window=60):
        """Singleton pattern to ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_requests=200, time_window=60):
        """
        Initialize rate limiter (only once due to singleton)
        :param max_requests: Maximum number of requests allowed
        :param time_window: Time window in seconds (default 60 for per minute)
        """
        if self._initialized:
            return
        
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_times = deque()
        self.min_interval = time_window / max_requests  # Minimum time between requests
        self._initialized = True
        
        # Initialize lock for thread safety
        import threading
        if RateLimiter._lock is None:
            RateLimiter._lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits (thread-safe)"""
        with RateLimiter._lock:
            current_time = time.time()
            
            # Remove requests older than the time window
            while self.request_times and current_time - self.request_times[0] > self.time_window:
                self.request_times.popleft()
            
            # Check if we've hit the limit
            if len(self.request_times) >= self.max_requests:
                # Calculate how long to wait
                oldest_request = self.request_times[0]
                wait_time = self.time_window - (current_time - oldest_request)
                if wait_time > 0:
                    _logger.info('Rate limit reached. Waiting %.2f seconds...', wait_time)
                    time.sleep(wait_time)
                    current_time = time.time()
                    # Clean up old requests again
                    while self.request_times and current_time - self.request_times[0] > self.time_window:
                        self.request_times.popleft()
            
            # Add minimum interval between requests for smooth distribution
            if self.request_times:
                time_since_last = current_time - self.request_times[-1]
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    time.sleep(wait_time)
                    current_time = time.time()
            
            # Record this request
            self.request_times.append(current_time)


class TesoteAPI(models.AbstractModel):
    _name = 'tesote.api'
    _description = 'Tesote API Connector'
    
    API_BASE_URL = 'https://equipo.tesote.com/api/v2'
    
    # Singleton rate limiter shared across all instances
    _rate_limiter = RateLimiter(max_requests=190, time_window=60)
    
    @api.model
    def _get_api_key(self):
        """Get API key from settings"""
        key = self.env['ir.config_parameter'].sudo().get_param('tesote.api_key')
        if not key:
            raise UserError(_('Tesote API key not configured. Please go to Settings > Accounting.'))
        return key
    
    @api.model
    def _make_request(self, endpoint, method='GET', params=None, json_data=None, max_retries=3):
        """
        Make API request to Tesote with retry logic and rate limiting
        
        :param endpoint: API endpoint
        :param method: HTTP method (GET, POST)
        :param params: Query parameters
        :param json_data: JSON data for POST requests
        :param max_retries: Maximum number of retry attempts
        :return: JSON response
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self._get_api_key()}',
            'Content-Type': 'application/json'
        }
        
        retry_count = 0
        last_error = None
        
        # Errors that should trigger a retry
        retryable_status_codes = {429, 500, 502, 503, 504}
        
        while retry_count <= max_retries:
            try:
                # Apply rate limiting before making the request
                self._rate_limiter.wait_if_needed()
                
                # Make the request
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, json=json_data, timeout=30)
                else:
                    raise UserError(_('Unsupported HTTP method'))
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Success - return the JSON response
                if retry_count > 0:
                    _logger.info('Request succeeded after %d retries', retry_count)
                return response.json()
                
            except requests.exceptions.Timeout as e:
                last_error = e
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                    _logger.warning('Tesote API timeout (attempt %d/%d). Retrying in %d seconds...',
                                  retry_count, max_retries + 1, wait_time)
                    time.sleep(wait_time)
                else:
                    _logger.error('Tesote API timeout after %d attempts', retry_count)
                    raise UserError(_('Tesote API timeout after %d attempts. Please try again later.') % retry_count)
            
            except requests.exceptions.ConnectionError as e:
                last_error = e
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    _logger.warning('Connection error (attempt %d/%d). Retrying in %d seconds...',
                                  retry_count, max_retries + 1, wait_time)
                    time.sleep(wait_time)
                else:
                    _logger.error('Connection error after %d attempts', retry_count)
                    raise UserError(_('Cannot connect to Tesote API after %d attempts. Please check your internet connection.') % retry_count)
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                
                # Handle specific error codes
                if status_code == 401:
                    raise UserError(_('Invalid Tesote API key. Please check your configuration.'))
                
                elif status_code == 429:
                    # Rate limit exceeded - apply backoff and retry
                    retry_count += 1
                    if retry_count <= max_retries:
                        # Try to get retry-after header
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after and retry_after.isdigit():
                            wait_time = int(retry_after)
                        else:
                            wait_time = 2 ** retry_count * 5  # Longer backoff for rate limits: 10, 20, 40 seconds
                        
                        _logger.warning('Rate limit exceeded (attempt %d/%d). Waiting %d seconds...',
                                      retry_count, max_retries + 1, wait_time)
                        time.sleep(wait_time)
                    else:
                        raise UserError(_('Tesote API rate limit exceeded after %d attempts. Please try again later.') % retry_count)
                
                elif status_code in retryable_status_codes:
                    # Server errors - retry with backoff
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        _logger.warning('Server error %d (attempt %d/%d). Retrying in %d seconds...',
                                      status_code, retry_count, max_retries + 1, wait_time)
                        time.sleep(wait_time)
                    else:
                        raise UserError(_('Tesote API error %d after %d attempts. Please try again later.') % (status_code, retry_count))
                
                else:
                    # Non-retryable error
                    _logger.error('Tesote API HTTP error %d: %s', status_code, str(e))
                    raise UserError(_('Tesote API error: %s') % str(e))
            
            except Exception as e:
                _logger.error('Unexpected Tesote API error: %s', str(e))
                raise UserError(_('Unexpected error connecting to Tesote: %s') % str(e))
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
    
    @api.model
    def test_connection(self):
        """Test API connection"""
        try:
            result = self._make_request('/status')
            if result.get('authenticated'):
                return {
                    'success': True,
                    'message': _('Connection successful!'),
                    'version': result.get('version', 'Unknown')
                }
            else:
                return {
                    'success': False,
                    'message': _('Authentication failed')
                }
        except UserError as e:
            return {
                'success': False,
                'message': str(e.args[0])
            }
    
    @api.model
    def get_accounts(self):
        """Get all accounts from Tesote with automatic pagination"""
        accounts = []
        page = 1
        max_pages = 100  # Safety limit increased due to rate limiting
        
        _logger.info('Fetching accounts from Tesote API...')
        
        while page <= max_pages:
            try:
                result = self._make_request('/accounts', params={'page': page, 'per_page': 50})
                page_accounts = result.get('accounts', [])
                accounts.extend(page_accounts)
                
                _logger.info('Fetched page %d: %d accounts', page, len(page_accounts))
                
                pagination = result.get('pagination', {})
                total_pages = pagination.get('total_pages', 1)
                
                # Safety checks
                if not pagination:
                    _logger.warning('No pagination info received, stopping')
                    break
                if page >= total_pages:
                    _logger.info('Reached last page (%d/%d)', page, total_pages)
                    break
                if not page_accounts:
                    _logger.warning('Empty accounts list received on page %d, stopping', page)
                    break
                    
                page += 1
                
            except Exception as e:
                _logger.error('Error fetching accounts page %d: %s', page, str(e))
                # If we already have some accounts, return them
                if accounts:
                    _logger.warning('Returning %d accounts fetched before error', len(accounts))
                    break
                else:
                    raise
        
        if page > max_pages:
            _logger.warning('Maximum pages limit reached (%d), some accounts may be missing', max_pages)
        
        _logger.info('Successfully fetched %d total accounts', len(accounts))
        return accounts
    
    @api.model
    def get_transactions(self, account_id, date_from=None, date_to=None):
        """
        Get transactions for a specific account with date filtering
        Includes automatic pagination, retry logic, and rate limiting
        """
        transactions = []
        after_id = None
        max_iterations = 100  # Safety limit increased due to rate limiting
        iteration_count = 0
        
        params = {'per_page': 100}
        if date_from:
            params['start_date'] = date_from.strftime('%Y-%m-%d')
        if date_to:
            params['end_date'] = date_to.strftime('%Y-%m-%d')
        
        _logger.info('Fetching transactions for account %s from %s to %s',
                    account_id, params.get('start_date', 'beginning'), params.get('end_date', 'today'))
        
        while iteration_count < max_iterations:
            iteration_count += 1
            
            try:
                if after_id:
                    params['transactions_after_id'] = after_id
                
                # Make request with retry logic included in _make_request
                result = self._make_request(f'/accounts/{account_id}/transactions', params=params)
                
                # Get transactions from response
                new_transactions = result.get('transactions', [])
                if not new_transactions and iteration_count > 1:
                    _logger.info('No more transactions received after %d iterations', iteration_count)
                    break
                    
                transactions.extend(new_transactions)
                _logger.info('Iteration %d: fetched %d transactions (total: %d)',
                           iteration_count, len(new_transactions), len(transactions))
                
                # Check pagination info
                pagination = result.get('pagination', {})
                if not pagination:
                    _logger.warning('No pagination info in response, stopping')
                    break
                    
                # Check if there are more pages
                if not pagination.get('has_more', False):
                    _logger.info('No more pages available')
                    break
                
                # Get next cursor/after_id
                new_after_id = pagination.get('after_id')
                if not new_after_id:
                    _logger.warning('No after_id in pagination, stopping')
                    break
                    
                # Safety check: ensure we're not stuck in same position
                if new_after_id == after_id:
                    _logger.error('Pagination cursor not advancing, stopping to prevent infinite loop')
                    break
                    
                after_id = new_after_id
                
            except UserError:
                # UserError already logged and formatted, just re-raise
                raise
            except Exception as e:
                _logger.error('Unexpected error fetching transactions on iteration %d: %s',
                            iteration_count, str(e))
                raise UserError(_('Failed to fetch transactions: %s') % str(e))
        
        if iteration_count >= max_iterations:
            _logger.warning('Maximum iterations reached (%d), some transactions may be missing', max_iterations)
            raise UserError(_('Transaction fetch exceeded maximum pages (%d). Please use smaller date ranges.') 
                          % max_iterations)
        
        _logger.info('Successfully fetched %d total transactions in %d iterations', 
                    len(transactions), iteration_count)
        
        return transactions