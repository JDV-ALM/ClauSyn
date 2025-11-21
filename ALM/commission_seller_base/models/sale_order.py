from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        tracking=True,
        help='Vendedor responsable de este pedido que recibirá comisión'
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_commission_seller(self):
        """Heredar vendedor del contacto o sugerir basado en el último pedido"""
        if self.partner_id:
            # Primero intentar heredar del contacto
            if self.partner_id.commission_seller_id:
                self.commission_seller_id = self.partner_id.commission_seller_id
            else:
                # Si no tiene vendedor asignado, buscar el último pedido de este cliente
                last_order = self.search([
                    ('partner_id', '=', self.partner_id.id),
                    ('commission_seller_id', '!=', False),
                    ('id', '!=', self._origin.id),
                ], limit=1, order='date_order desc, id desc')
                
                if last_order:
                    self.commission_seller_id = last_order.commission_seller_id
    
    def _prepare_invoice(self):
        """Propagar el vendedor a la factura"""
        invoice_vals = super()._prepare_invoice()
        if self.commission_seller_id:
            invoice_vals['commission_seller_id'] = self.commission_seller_id.id
        return invoice_vals