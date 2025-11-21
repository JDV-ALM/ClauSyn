from odoo import fields, models, api
from datetime import date


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        tracking=True,
        help='Vendedor responsable de esta factura que recibirá comisión'
    )
    
    commission_reception_date = fields.Date(
        string='Fecha de Recepción',
        tracking=True,
        help='Fecha en que se recibió la factura. Se usa para los períodos de cálculo de comisiones.'
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_commission_seller(self):
        """Heredar vendedor del contacto o sugerir basado en la última factura"""
        if self.partner_id and self.move_type in ['out_invoice', 'out_refund']:
            # Primero intentar heredar del contacto
            if self.partner_id.commission_seller_id:
                self.commission_seller_id = self.partner_id.commission_seller_id
            else:
                # Si no tiene vendedor asignado, buscar la última factura de este cliente
                last_invoice = self.search([
                    ('partner_id', '=', self.partner_id.id),
                    ('commission_seller_id', '!=', False),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('id', '!=', self._origin.id),
                ], limit=1, order='invoice_date desc, id desc')
                
                if last_invoice:
                    self.commission_seller_id = last_invoice.commission_seller_id