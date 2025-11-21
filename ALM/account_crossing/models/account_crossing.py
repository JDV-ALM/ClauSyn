# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountCrossing(models.Model):
    _name = 'account.crossing'
    _description = 'Cruce Contable'
    _order = 'crossing_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Número',
        required=True,
        readonly=True,
        copy=False,
        default='/',
        tracking=True
    )
    crossing_date = fields.Date(
        string='Fecha de Cruce',
        required=True,
        default=fields.Date.context_today,
        readonly=True,
        states={'draft': [('readonly', False)]},
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        readonly=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        store=True
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        readonly=True,
        ondelete='restrict',
        domain="[('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']), "
               "('state', '=', 'posted'), ('payment_state', '!=', 'paid')]"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        related='move_id.partner_id',
        store=True,
        readonly=True
    )
    move_type = fields.Selection(
        related='move_id.move_type',
        string='Tipo de Documento',
        store=True,
        readonly=True
    )
    crossing_reason_id = fields.Many2one(
        'account.crossing.reason',
        string='Motivo de Cruce',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        tracking=True
    )
    journal_entry_id = fields.Many2one(
        'account.move',
        string='Asiento Contable',
        readonly=True,
        ondelete='restrict',
        copy=False
    )
    amount = fields.Monetary(
        string='Monto',
        required=True,
        readonly=True,
        tracking=True
    )
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        tracking=True,
        help='Vendedor responsable que recibirá comisión por este cruce'
    )
    notes = fields.Text(
        string='Notas',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', required=True, readonly=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                sequence_code = 'account.crossing'
                company_id = vals.get('company_id', self.env.company.id)
                vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code(sequence_code) or '/'
        return super().create(vals_list)

    def action_post(self):
        """Confirma el cruce y crea el asiento contable"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Solo puede confirmar cruces en estado borrador.'))
            
            # Crear asiento contable
            move_vals = record._prepare_account_move_vals()
            journal_entry = self.env['account.move'].create(move_vals)
            journal_entry.action_post()
            
            # Reconciliar
            record._reconcile_moves(journal_entry)
            
            record.write({
                'state': 'posted',
                'journal_entry_id': journal_entry.id
            })
            
            # Mensaje en el chatter
            record.message_post(
                body=_('Cruce confirmado: %s por %s %s') % (
                    record.crossing_reason_id.display_name,
                    record.amount,
                    record.currency_id.symbol
                )
            )
        return True

    def action_cancel(self):
        """Cancela el cruce y reversa el asiento contable"""
        for record in self:
            if record.state != 'posted':
                raise UserError(_('Solo puede cancelar cruces confirmados.'))
            
            if record.journal_entry_id:
                # Reversar asiento
                reverse_move = record.journal_entry_id._reverse_moves(
                    default_values_list=[{
                        'date': fields.Date.context_today(self),
                        'ref': _('Reverso de: %s') % record.name
                    }]
                )
                reverse_move.action_post()
            
            record.write({'state': 'cancelled'})
            record.message_post(body=_('Cruce cancelado'))
        return True

    def action_draft(self):
        """Regresa el cruce a borrador"""
        for record in self:
            if record.state != 'cancelled':
                raise UserError(_('Solo puede regresar a borrador cruces cancelados.'))
            record.write({'state': 'draft'})
        return True

    def _prepare_account_move_vals(self):
        """Prepara los valores para crear el asiento contable"""
        self.ensure_one()
        
        # Determinar el contacto de contrapartida
        counterpart_partner = self.crossing_reason_id.counterpart_partner_id or self.partner_id
        
        # Determinar cuentas según tipo de documento
        if self.move_type in ['out_invoice', 'out_refund']:
            # Factura de cliente: Debito a cuenta cruce, Crédito a CxC
            receivable_account = self.move_id.partner_id.property_account_receivable_id
            debit_account = self.crossing_reason_id.account_id
            credit_account = receivable_account
            # Partner de débito es el de contrapartida, crédito es el cliente original
            debit_partner = counterpart_partner
            credit_partner = self.partner_id
        else:
            # Factura de proveedor: Debito a CxP, Crédito a cuenta cruce
            payable_account = self.move_id.partner_id.property_account_payable_id
            debit_account = payable_account
            credit_account = self.crossing_reason_id.account_id
            # Partner de débito es el proveedor original, crédito es el de contrapartida
            debit_partner = self.partner_id
            credit_partner = counterpart_partner

        line_vals = [
            (0, 0, {
                'name': f"{self.crossing_reason_id.name} - {self.move_id.name}",
                'account_id': debit_account.id,
                'partner_id': debit_partner.id,
                'debit': self.amount,
                'credit': 0.0,
            }),
            (0, 0, {
                'name': f"{self.crossing_reason_id.name} - {self.move_id.name}",
                'account_id': credit_account.id,
                'partner_id': credit_partner.id,
                'debit': 0.0,
                'credit': self.amount,
            })
        ]

        return {
            'move_type': 'entry',
            'date': self.crossing_date,
            'journal_id': self.crossing_reason_id.journal_id.id,
            'ref': f"{self.name} - {self.move_id.name}",
            'line_ids': line_vals,
            'company_id': self.company_id.id,
        }

    def _reconcile_moves(self, journal_entry):
        """Reconcilia el asiento de cruce con la factura original"""
        self.ensure_one()
        
        # Obtener líneas a reconciliar
        if self.move_type in ['out_invoice', 'out_refund']:
            account = self.move_id.partner_id.property_account_receivable_id
        else:
            account = self.move_id.partner_id.property_account_payable_id
        
        lines_to_reconcile = (self.move_id.line_ids | journal_entry.line_ids).filtered(
            lambda l: l.account_id == account and not l.reconciled
        )
        
        if lines_to_reconcile:
            lines_to_reconcile.reconcile()

    def unlink(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('No puede eliminar cruces confirmados. Debe cancelarlos primero.'))
        return super().unlink()