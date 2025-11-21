# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    crossing_ids = fields.One2many(
        'account.crossing',
        'move_id',
        string='Cruces Contables',
        readonly=True
    )
    crossing_count = fields.Integer(
        string='Número de Cruces',
        compute='_compute_crossing_count',
        store=True
    )
    has_crossings = fields.Boolean(
        string='Tiene Cruces',
        compute='_compute_crossing_count',
        store=True
    )

    @api.depends('crossing_ids')
    def _compute_crossing_count(self):
        for record in self:
            record.crossing_count = len(record.crossing_ids)
            record.has_crossings = bool(record.crossing_ids)

    def action_register_crossing(self):
        """Abre el wizard de cruce contable"""
        self.ensure_one()
        
        # Validaciones
        if self.state != 'posted':
            raise UserError(_('Solo puede realizar cruces en facturas confirmadas.'))
        
        if self.payment_state == 'paid':
            raise UserError(_('La factura ya está pagada completamente.'))
        
        if self.move_type not in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            raise UserError(_('Solo puede realizar cruces en facturas.'))

        # Calcular monto pendiente
        amount_residual = abs(self.amount_residual)
        
        return {
            'name': _('Registro de Cruce Contable'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.crossing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_company_id': self.company_id.id,
                'default_amount': amount_residual,
                'default_currency_id': self.currency_id.id,
            }
        }

    def action_view_crossings(self):
        """Muestra los cruces relacionados con esta factura"""
        self.ensure_one()
        
        action = {
            'name': _('Cruces Contables'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.crossing',
            'view_mode': 'tree,form',
            'domain': [('move_id', '=', self.id)],
            'context': {
                'default_move_id': self.id,
                'default_company_id': self.company_id.id,
            }
        }
        
        if self.crossing_count == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.crossing_ids[0].id,
            })
        
        return action