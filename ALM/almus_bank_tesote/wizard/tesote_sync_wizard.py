# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class TesoteSyncWizard(models.TransientModel):
    _name = 'tesote.sync.wizard'
    _description = 'Tesote Synchronization Wizard'
    
    journal_ids = fields.Many2many(
        'account.journal',
        string='Bank Journals',
        domain=[('type', 'in', ['bank', 'cash']), ('tesote_account_id', '!=', False)],
        help='Select journals to sync with Tesote'
    )
    
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today() - timedelta(days=7)
    )
    
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today
    )
    
    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('From Date cannot be after To Date')
                }
            }
    
    def action_sync(self):
        """Execute synchronization"""
        self.ensure_one()
        
        if not self.journal_ids:
            raise UserError(_('Please select at least one journal to sync'))
        
        if self.date_from > self.date_to:
            raise UserError(_('From Date cannot be after To Date'))
        
        tesote_api = self.env['tesote.api']
        created_statements = self.env['account.bank.statement']
        
        for journal in self.journal_ids:
            if not journal.tesote_account_id:
                _logger.warning('Journal %s has no Tesote account configured', journal.name)
                continue
            
            try:
                # Get transactions from Tesote
                transactions = tesote_api.get_transactions(
                    journal.tesote_account_id,
                    self.date_from,
                    self.date_to
                )
                
                if not transactions:
                    _logger.info('No transactions found for journal %s', journal.name)
                    continue
                
                # Filter out already imported transactions
                # IMPORTANT: Odoo adds prefixes to unique_import_id (account_number + journal_id)
                # We need to search for IDs that END with our pattern
                existing_lines = self.env['account.bank.statement.line'].search([
                    ('unique_import_id', 'like', f'%-tesote-{journal.tesote_account_id}-%')
                ])
                
                # Extract our original unique_import_ids (the part after the last occurrence of 'tesote')
                existing_import_ids = set()
                for line in existing_lines:
                    if line.unique_import_id and 'tesote' in line.unique_import_id:
                        # Find the last occurrence of 'tesote' and take everything from there
                        parts = line.unique_import_id.split('tesote-')
                        if len(parts) >= 2:
                            # Reconstruct: tesote-{account_id}-{transaction_id}
                            original_id = 'tesote-' + parts[-1]
                            existing_import_ids.add(original_id)
                
                # Filter only new transactions by constructing the expected unique_import_id
                new_transactions = []
                for tx in transactions:
                    # Construct the same unique_import_id that will be generated during import
                    expected_unique_id = f"tesote-{journal.tesote_account_id}-{tx.get('id')}"
                    
                    if expected_unique_id not in existing_import_ids:
                        new_transactions.append(tx)
                
                _logger.info('Journal %s: %d total transactions, %d already imported, %d new to import',
                           journal.name, len(transactions), 
                           len(transactions) - len(new_transactions), 
                           len(new_transactions))
                
                if not new_transactions:
                    _logger.info('No new transactions to import for journal %s', journal.name)
                    continue
                
                # Prepare data for import (only with new transactions)
                import_data = {
                    'account_id': journal.tesote_account_id,
                    'account_number': journal.bank_account_id.acc_number if journal.bank_account_id else '',
                    'currency': journal.currency_id.name or journal.company_id.currency_id.name,
                    'transactions': new_transactions,
                    'date_from': self.date_from.strftime('%Y-%m-%d'),
                    'date_to': self.date_to.strftime('%Y-%m-%d'),
                    'statement_name': f"Tesote Import {self.date_from} to {self.date_to}"
                }
                
                # Create attachment with JSON data
                # Add microseconds and random suffix to ensure uniqueness
                import uuid
                attachment_name = f'tesote_import_{journal.id}_{datetime.now().strftime("%Y%m%d_%H%M%S%f")}_{uuid.uuid4().hex[:8]}.json'
                
                attachment_data = base64.b64encode(json.dumps(import_data).encode('utf-8'))
                attachment = self.env['ir.attachment'].create({
                    'name': attachment_name,
                    'datas': attachment_data,
                    'mimetype': 'application/json',
                })
                
                # Import using Odoo's standard flow
                with self.env.cr.savepoint():
                    result = journal.with_context(tesote_import=True)._import_bank_statement(attachment)
                    
                    # Update last sync date
                    journal.tesote_last_sync = fields.Datetime.now()
                    
                _logger.info('Successfully synced %d transactions for journal %s', 
                           len(transactions), journal.name)
                
            except Exception as e:
                _logger.error('Error syncing journal %s: %s', journal.name, str(e))
                raise UserError(_('Error syncing journal %s: %s') % (journal.name, str(e)))
        
        # Return action to show imported statements
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Synchronization completed successfully'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.bank.statement.line',
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'domain': [('journal_id', 'in', self.journal_ids.ids)],
                    'context': {'search_default_not_matched': True},
                }
            }
        }
    
    @api.model
    def cron_sync_all(self):
        """Method called by cron to sync all enabled journals"""
        auto_sync = self.env['ir.config_parameter'].sudo().get_param('tesote.auto_sync')
        if not auto_sync:
            _logger.info('Tesote auto sync is disabled')
            return
        
        sync_days = int(self.env['ir.config_parameter'].sudo().get_param('tesote.sync_days', '7'))
        
        # Find all journals with Tesote sync enabled
        journals = self.env['account.journal'].search([
            ('tesote_sync_enabled', '=', True),
            ('tesote_account_id', '!=', False)
        ])
        
        if not journals:
            _logger.info('No journals configured for Tesote auto sync')
            return
        
        # Create wizard and execute sync
        wizard = self.create({
            'journal_ids': [(6, 0, journals.ids)],
            'date_from': fields.Date.today() - timedelta(days=sync_days),
            'date_to': fields.Date.today(),
        })
        
        try:
            wizard.action_sync()
            _logger.info('Tesote auto sync completed successfully')
        except Exception as e:
            _logger.error('Tesote auto sync failed: %s', str(e))
    
    def sync_from_webhook(self, account_ids=None):
        """Public method to be called from webhooks/automations"""
        if account_ids:
            # Find journals matching the account IDs
            journals = self.env['account.journal'].search([
                ('tesote_account_id', 'in', account_ids)
            ])
        else:
            # Sync all enabled journals
            journals = self.env['account.journal'].search([
                ('tesote_sync_enabled', '=', True),
                ('tesote_account_id', '!=', False)
            ])
        
        if not journals:
            _logger.warning('No journals found for webhook sync')
            return False
        
        # Create wizard with last 2 days of data
        wizard = self.create({
            'journal_ids': [(6, 0, journals.ids)],
            'date_from': fields.Date.today() - timedelta(days=2),
            'date_to': fields.Date.today(),
        })
        
        wizard.action_sync()
        return True