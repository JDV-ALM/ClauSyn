from odoo import fields, models, api


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        help='Vendedor responsable de este pago que recibirá comisión'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Obtener vendedor de las facturas seleccionadas"""
        res = super().default_get(fields_list)
        
        if self._context.get('active_model') == 'account.move':
            move_ids = self._context.get('active_ids', [])
            if move_ids:
                moves = self.env['account.move'].browse(move_ids)
                # Si todas las facturas tienen el mismo vendedor, usarlo por defecto
                sellers = moves.mapped('commission_seller_id')
                if len(sellers) == 1:
                    res['commission_seller_id'] = sellers.id
        
        return res
    
    def _create_payments(self):
        """Propagar el vendedor al pago creado"""
        self = self.with_context(commission_seller_id=self.commission_seller_id.id)
        return super()._create_payments()