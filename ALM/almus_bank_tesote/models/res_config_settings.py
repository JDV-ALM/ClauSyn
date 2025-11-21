# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    tesote_api_key = fields.Char(
        string='Tesote API Key',
        config_parameter='tesote.api_key'
    )
    
    tesote_sync_days = fields.Integer(
        string='Days to Sync',
        default=7,
        config_parameter='tesote.sync_days',
        help='Number of days to sync when running automatic synchronization'
    )
    
    tesote_auto_sync = fields.Boolean(
        string='Automatic Sync',
        config_parameter='tesote.auto_sync',
        help='Enable automatic synchronization via scheduled actions'
    )
    
    def action_tesote_test_connection(self):
        """Test Tesote API connection"""
        self.ensure_one()
        tesote_api = self.env['tesote.api']
        result = tesote_api.test_connection()
        
        if result['success']:
            message = _('Connection successful! API Version: %s') % result.get('version', 'Unknown')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': result['message'],
                    'type': 'danger',
                    'sticky': False,
                }
            }
    
    def action_tesote_fetch_accounts(self):
        """Fetch accounts from Tesote and update selection fields"""
        self.ensure_one()
        tesote_api = self.env['tesote.api']
        
        try:
            accounts = tesote_api.get_accounts()
            
            # Store accounts data for journal selection
            account_list = []
            for account in accounts:
                account_id = account.get('id')
                name = account.get('name', 'Unknown')
                bank = account.get('bank', {}).get('name', '')
                currency = account.get('data', {}).get('currency', '')
                
                display_name = f"{bank} - {name} ({currency})"
                account_list.append(f"{account_id}|{display_name}")
            
            # Save to system parameter
            self.env['ir.config_parameter'].sudo().set_param(
                'tesote.accounts_list', 
                '||'.join(account_list)
            )
            
            message = _('Successfully fetched %d accounts from Tesote') % len(accounts)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }