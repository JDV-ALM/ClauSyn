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
        domain="[('account_type', 'in', ['liability_current', 'liability_non_current']), ('deprecated', '=', False)]",
        help='Cuenta contable para registrar los anticipos de reservas hoteleras'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    hotel_advance_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Anticipos',
        related='company_id.hotel_advance_account_id',
        readonly=False,
        domain="[('account_type', 'in', ['liability_current', 'liability_non_current']), ('deprecated', '=', False), ('company_id', '=', company_id)]",
        help='Cuenta contable de pasivo para registrar los anticipos recibidos de clientes. Esta cuenta se usará hasta que se genere la factura y se concilie el pago.'
    )
    
    @api.constrains('hotel_advance_account_id')
    def _check_advance_account(self):
        for record in self:
            if record.hotel_advance_account_id:
                if record.hotel_advance_account_id.account_type not in ['liability_current', 'liability_non_current']:
                    raise ValidationError(_('La cuenta de anticipos debe ser una cuenta de pasivo (Pasivo Corriente o No Corriente)'))
                if record.hotel_advance_account_id.deprecated:
                    raise ValidationError(_('No se puede usar una cuenta deprecada para anticipos'))
    
    def set_values(self):
        """Override para validar antes de guardar"""
        if self.hotel_advance_account_id:
            # Validar que la cuenta sea apropiada
            if self.hotel_advance_account_id.account_type not in ['liability_current', 'liability_non_current']:
                raise ValidationError(_(
                    'La cuenta seleccionada "%s" no es una cuenta de pasivo. '
                    'Por favor seleccione una cuenta de tipo Pasivo Corriente o Pasivo No Corriente.'
                ) % self.hotel_advance_account_id.display_name)
        
        return super().set_values()
    
    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        res.update({
            'hotel_advance_account_id': company.hotel_advance_account_id.id if company.hotel_advance_account_id else False,
        })
        return res