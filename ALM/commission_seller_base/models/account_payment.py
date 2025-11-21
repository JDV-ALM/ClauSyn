from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        tracking=True,
        help='Vendedor responsable de este pago que recibirá comisión'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Heredar vendedor del wizard si viene de ahí"""
        for vals in vals_list:
            if self.env.context.get('commission_seller_id') and not vals.get('commission_seller_id'):
                vals['commission_seller_id'] = self.env.context.get('commission_seller_id')
        return super().create(vals_list)
    
    @api.onchange('partner_id')
    def _onchange_partner_commission_seller(self):
        """Heredar vendedor del contacto o sugerir basado en facturas relacionadas"""
        if self.partner_id and self.partner_type == 'customer':
            # Primero intentar heredar del contacto
            if self.partner_id.commission_seller_id:
                self.commission_seller_id = self.partner_id.commission_seller_id
            else:
                # Si no tiene vendedor asignado, buscar facturas abiertas de este cliente
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('commission_seller_id', '!=', False),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ], limit=1, order='invoice_date desc')
                
                if invoices:
                    self.commission_seller_id = invoices[0].commission_seller_id