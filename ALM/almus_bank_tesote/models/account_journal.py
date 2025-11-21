# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    tesote_account_id = fields.Selection(
        selection='_selection_tesote_accounts',
        string='Tesote Account',
        help='Select a Tesote account to sync with this journal'
    )
    
    @api.model
    def _selection_tesote_accounts(self):
        """Dynamic selection of Tesote accounts"""
        accounts_list = self.env['ir.config_parameter'].sudo().get_param('tesote.accounts_list', '')
        selection = []
        
        if accounts_list:
            for account_data in accounts_list.split('||'):
                if '|' in account_data:
                    acc_id, acc_name = account_data.split('|', 1)
                    selection.append((acc_id, acc_name))
        
        return selection or [('', 'No accounts available - Run "Fetch Accounts" in Settings')]
    tesote_sync_enabled = fields.Boolean(
        string='Enable Tesote Sync',
        default=False,
        help='Enable automatic synchronization with Tesote'
    )
    
    tesote_last_sync = fields.Datetime(
        string='Last Tesote Sync',
        readonly=True
    )
    
    @api.model
    def _selection_tesote_accounts(self):
        """Dynamic selection of Tesote accounts"""
        accounts_list = self.env['ir.config_parameter'].sudo().get_param('tesote.accounts_list', '')
        selection = []
        
        if accounts_list:
            for account_data in accounts_list.split('||'):
                if '|' in account_data:
                    acc_id, acc_name = account_data.split('|', 1)
                    selection.append((acc_id, acc_name))
        
        return selection or [('', 'No accounts available - Run "Fetch Accounts" in Settings')]
    
    def _parse_bank_statement_file(self, attachment):
        """Override to handle Tesote format"""
        # Check if this is a Tesote import
        if self._context.get('tesote_import'):
            return self._parse_tesote_file(attachment)
        return super()._parse_bank_statement_file(attachment)
    
    def _parse_tesote_file(self, attachment):
        """Parse Tesote transactions data"""
        import json
        
        # The attachment contains JSON data from Tesote
        try:
            data = json.loads(attachment.raw.decode('utf-8'))
        except Exception as e:
            _logger.error('Failed to parse Tesote data: %s', str(e))
            return super()._parse_bank_statement_file(attachment)
        
        currency_code = data.get('currency', self.currency_id.name or self.company_id.currency_id.name)
        account_number = data.get('account_number', self.bank_account_id.acc_number if self.bank_account_id else '')
        
        transactions = []
        
        for tx in data.get('transactions', []):
            tx_data = tx.get('data', {})
            amount = tx_data.get('amount_cents', 0) / 100.0
            
            transaction = {
                'name': tx_data.get('description', 'Transaction'),  # Etiqueta principal
                'date': tx_data.get('transaction_date'),
                'amount': amount,
                'unique_import_id': f"tesote-{data.get('account_id')}-{tx.get('id')}",
                'ref': tx_data.get('external_service_id', ''),  # Referencia del banco
                'payment_ref': tx_data.get('description', ''),  # Descripción original como referencia de pago
                'narration': tx_data.get('note', ''),  # Notas adicionales
            }
            
            # Add partner info if available
            if tx.get('counterparty'):
                counterparty = tx['counterparty']
                transaction['partner_name'] = counterparty.get('name', '')
                transaction['account_number'] = counterparty.get('account_number', '')
            
            transactions.append(transaction)
        
        # Let Odoo handle balance calculation
        # We don't specify balance_start or balance_end_real
        # Odoo will use the previous statement's ending balance as starting balance
        # and calculate the ending balance from the transactions
        vals = {
            'name': data.get('statement_name', f"Import {datetime.now().strftime('%Y-%m-%d')}"),
            'date': data.get('date_to', fields.Date.today()),
            'transactions': transactions,
        }
        
        return currency_code, account_number, [vals]
    
    def action_sync_tesote(self):
        """Manual sync action from journal"""
        self.ensure_one()
        if not self.tesote_account_id:
            raise UserError(_('No Tesote account configured for this journal'))
        
        # Open sync wizard with this journal pre-selected
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync from Tesote'),
            'res_model': 'tesote.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_journal_ids': [(6, 0, [self.id])],
                'default_date_from': fields.Date.today(),
                'default_date_to': fields.Date.today(),
            }
        }