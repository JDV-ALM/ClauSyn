from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_commission_seller = fields.Boolean(
        string='Es Vendedor',
        default=False,
        help='Marque esta casilla si este contacto es un vendedor de comisiones'
    )
    
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        tracking=True,
        help='Vendedor asignado a este contacto. Se heredará automáticamente en pedidos, facturas y pagos'
    )
    
    # Campos informativos para vendedores
    commission_payment_ids = fields.One2many(
        'account.payment',
        'commission_seller_id',
        string='Pagos Relacionados',
        readonly=True
    )
    
    commission_invoice_ids = fields.One2many(
        'account.move',
        'commission_seller_id',
        string='Facturas Relacionadas',
        domain=[('move_type', 'in', ['out_invoice', 'out_refund'])],
        readonly=True
    )
    
    commission_sale_ids = fields.One2many(
        'sale.order',
        'commission_seller_id',
        string='Órdenes de Venta Relacionadas',
        readonly=True
    )
    
    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=100, order=None):
        """Optimización para búsqueda de vendedores"""
        domain = domain or []
        if self.env.context.get('search_commission_seller'):
            domain = [('is_commission_seller', '=', True)] + domain
        return super()._name_search(name, domain, operator, limit, order)