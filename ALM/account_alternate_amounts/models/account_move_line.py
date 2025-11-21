# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    # Campo para almacenar la tasa de cambio a USD
    currency_rate_usd = fields.Float(
        string='Tasa USD',
        compute='_compute_alternate_amounts',
        store=True,
        digits=(12, 2),
        help='Cuántas unidades de moneda local equivalen a 1 USD'
    )
    
    debit_alternate = fields.Monetary(
        string='Débito USD',
        currency_field='usd_currency_id',
        compute='_compute_alternate_amounts',
        store=True,
        readonly=True,
        help='Débito en USD según tasa del día'
    )
    
    credit_alternate = fields.Monetary(
        string='Crédito USD',
        currency_field='usd_currency_id',
        compute='_compute_alternate_amounts',
        store=True,
        readonly=True,
        help='Crédito en USD según tasa del día'
    )
    
    # Campo para referenciar la moneda USD
    usd_currency_id = fields.Many2one(
        'res.currency',
        string='USD Currency',
        compute='_compute_usd_currency',
        store=True
    )
    
    @api.depends('company_id')
    def _compute_usd_currency(self):
        """Obtiene la referencia a la moneda USD"""
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        for line in self:
            line.usd_currency_id = usd.id if usd else False
    
    @api.depends('debit', 'credit', 'date', 'company_currency_id', 'move_id.date', 'move_id.invoice_date')
    def _compute_alternate_amounts(self):
        """Calcula los montos en USD basándose en la tasa de cambio del día"""
        for line in self:
            # Obtener moneda USD
            usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            
            if not usd_currency:
                line.debit_alternate = 0.0
                line.credit_alternate = 0.0
                line.currency_rate_usd = 0.0
                continue
            
            # Usar la fecha de la factura, del asiento o de la línea
            date_to_use = line.move_id.invoice_date or line.date or line.move_id.date or fields.Date.today()
            
            # Si la moneda de la compañía ya es USD, copiar directamente
            if line.company_currency_id and line.company_currency_id.id == usd_currency.id:
                line.debit_alternate = line.debit
                line.credit_alternate = line.credit
                line.currency_rate_usd = 1.0
            else:
                # Convertir de la moneda de la compañía a USD
                if line.company_currency_id:
                    # Obtener la tasa de cambio para la fecha específica
                    from_currency = line.company_currency_id
                    
                    # Calcular el monto en USD
                    debit_usd = from_currency._convert(
                        line.debit,
                        usd_currency,
                        line.company_id or self.env.company,
                        date_to_use
                    )
                    
                    credit_usd = from_currency._convert(
                        line.credit,
                        usd_currency,
                        line.company_id or self.env.company,
                        date_to_use
                    )
                    
                    # Calcular la tasa de cambio (cuántos de moneda local = 1 USD)
                    if line.debit > 0:
                        line.currency_rate_usd = line.debit / debit_usd if debit_usd else 0.0
                    elif line.credit > 0:
                        line.currency_rate_usd = line.credit / credit_usd if credit_usd else 0.0
                    else:
                        rate = from_currency._get_conversion_rate(
                            from_currency,
                            usd_currency,
                            line.company_id or self.env.company,
                            date_to_use
                        )
                        # Invertir para mostrar cuántos de moneda local = 1 USD
                        line.currency_rate_usd = 1 / rate if rate else 0.0
                    
                    line.debit_alternate = debit_usd
                    line.credit_alternate = credit_usd
                else:
                    line.debit_alternate = 0.0
                    line.credit_alternate = 0.0
                    line.currency_rate_usd = 0.0
