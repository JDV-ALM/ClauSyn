# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Campo para almacenar la tasa de cambio a USD del asiento
    currency_rate_usd = fields.Float(
        string='Tasa USD',
        compute='_compute_currency_rate_usd',
        store=True,
        digits=(12, 2),
        help='Cuántas unidades de moneda local equivalen a 1 USD'
    )
    
    @api.depends('date', 'invoice_date', 'company_currency_id')
    def _compute_currency_rate_usd(self):
        """Calcula la tasa de cambio de la moneda de la compañía a USD"""
        for move in self:
            # Obtener moneda USD
            usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            
            if not usd_currency:
                move.currency_rate_usd = 0.0
                continue
            
            # Usar la fecha de la factura o la fecha del asiento
            date_to_use = move.invoice_date or move.date or fields.Date.today()
            
            # Si la moneda de la compañía ya es USD
            if move.company_currency_id and move.company_currency_id.id == usd_currency.id:
                move.currency_rate_usd = 1.0
            else:
                # Obtener la tasa de cambio de la moneda de la compañía a USD
                if move.company_currency_id:
                    from_currency = move.company_currency_id
                    
                    # Calcular cuántas unidades de moneda local equivalen a 1 USD
                    rate = from_currency._get_conversion_rate(
                        from_currency,
                        usd_currency,
                        move.company_id or self.env.company,
                        date_to_use
                    )
                    
                    # Invertir la tasa para mostrar cuántos de moneda local = 1 USD
                    move.currency_rate_usd = 1 / rate if rate else 0.0
                else:
                    move.currency_rate_usd = 0.0
