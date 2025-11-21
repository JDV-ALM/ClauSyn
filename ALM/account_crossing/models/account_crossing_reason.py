# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountCrossingReason(models.Model):
    _name = 'account.crossing.reason'
    _description = 'Motivo de Cruce Contable'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Código',
        required=True,
        size=10
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta Contable',
        required=True,
        domain="[('account_type', 'not in', ['asset_receivable', 'liability_payable'])]",
        help='Cuenta contable contra la cual se realizará el cruce'
    )
    counterpart_partner_id = fields.Many2one(
        'res.partner',
        string='Contacto de Contrapartida',
        help='Contacto que se asignará a la línea de contrapartida del asiento contable. '
             'Útil para cruces intercompañía donde se requiere especificar la empresa destino.'
    )
    invert_balance_sign = fields.Boolean(
        string='Invertir Signo del Saldo',
        default=False,
        help='Activa esta opción para invertir la visualización del signo del saldo en el wizard. '
             'Útil para cuentas de pasivo (ej: Anticipos Recibidos) donde un saldo crédito '
             'representa disponibilidad positiva.'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario Contable',
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        help='Diario donde se registrará el asiento de cruce'
    )
    description = fields.Text(
        string='Descripción',
        translate=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    _sql_constraints = [
        ('code_company_unique', 'unique(code, company_id)', 
         'El código del motivo debe ser único por compañía!'),
    ]

    @api.constrains('account_id')
    def _check_account_type(self):
        for record in self:
            if record.account_id.account_type in ['asset_receivable', 'liability_payable']:
                raise ValidationError(_(
                    'No puede seleccionar una cuenta por cobrar o por pagar como cuenta de cruce. '
                    'Por favor seleccione otro tipo de cuenta.'
                ))

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}" if record.code else record.name

    def name_get(self):
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}" if record.code else record.name
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if operator in ('ilike', 'like', '=', '=like', '=ilike'):
            domain = ['|', ('code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)