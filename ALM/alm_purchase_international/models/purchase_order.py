# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    is_international = fields.Boolean(
        string='Compra Internacional',
        default=False,
        tracking=True,
        help='Marcar si esta orden de compra es internacional. '
             'Solo será visible para usuarios con permisos de compras internacionales.',
        states={'cancel': [('readonly', True)], 'done': [('readonly', True)]},
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_id_international(self):
        """
        Sugerencia automática basada en el país del proveedor.
        Solo sugiere, no fuerza el valor.
        """
        if self.partner_id and self.company_id:
            # Si el país del proveedor es diferente al de la compañía
            if (self.partner_id.country_id and 
                self.company_id.country_id and 
                self.partner_id.country_id != self.company_id.country_id):
                self.is_international = True