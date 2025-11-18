# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    hotel_advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Anticipos de Hotel',
        domain="[('deprecated', '=', False), ('company_id', '=', id), ('reconcile', '=', True)]",
        help='Cuenta contable para registrar los anticipos de reservas hoteleras. '
             'IMPORTANTE: Debe ser una cuenta reconciliable de tipo Pasivo (ej: Pasivo Corriente).'
    )

    alternative_hotel_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Alternativa Hotel',
        help='Moneda de referencia para mostrar deudas y saldos del hotel. '
             'En economías inflacionarias, permite preservar el valor real de las deudas. '
             'Ejemplo: USD en Venezuela, EUR en países con moneda inestable.'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    hotel_advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Anticipos',
        related='company_id.hotel_advance_account_id',
        readonly=False,
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('reconcile', '=', True)]",
        help='Cuenta contable para registrar los anticipos recibidos de clientes. '
             'IMPORTANTE: Debe ser una cuenta reconciliable de tipo Pasivo (ej: Pasivo Corriente). '
             'Esta cuenta se usará hasta que se genere la factura y se concilie el pago.'
    )

    alternative_hotel_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Alternativa Hotel',
        related='company_id.alternative_hotel_currency_id',
        readonly=False,
        help='Moneda de referencia para mostrar deudas y saldos del hotel. '
             'En economías inflacionarias, permite preservar el valor real de las deudas. '
             'Los pagos se registran en su moneda original y se convierten a esta moneda alternativa. '
             'Ejemplo: USD en Venezuela, EUR en países con moneda inestable.'
    )
    
    @api.constrains('hotel_advance_account_id')
    def _check_advance_account(self):
        for record in self:
            if record.hotel_advance_account_id:
                if record.hotel_advance_account_id.deprecated:
                    raise ValidationError(_('No se puede usar una cuenta deprecada para anticipos'))
                # IMPORTANTE: La cuenta debe ser reconciliable para que funcione con account.payment
                if not record.hotel_advance_account_id.reconcile:
                    raise ValidationError(_(
                        'La cuenta de anticipos "%s" debe ser reconciliable. '
                        'Por favor active la opción "Permitir Conciliación" en la configuración de la cuenta.'
                    ) % record.hotel_advance_account_id.display_name)
    
    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        res.update({
            'hotel_advance_account_id': company.hotel_advance_account_id.id if company.hotel_advance_account_id else False,
        })
        return res