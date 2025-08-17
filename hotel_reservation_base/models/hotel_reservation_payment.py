# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class HotelReservationPayment(models.Model):
    _name = 'hotel.reservation.payment'
    _description = 'Anticipo de Reserva'
    _order = 'payment_date desc, id desc'
    _inherit = ['mail.thread']
    
    reservation_id = fields.Many2one(
        'hotel.reservation',
        string='Reserva',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    name = fields.Char(
        string='Descripción',
        required=True,
        default='Anticipo'
    )
    
    amount = fields.Monetary(
        string='Monto',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de Pago',
        required=True,
        domain=[('active', '=', True)]
    )
    
    payment_date = fields.Datetime(
        string='Fecha de Pago',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain=[('type', 'in', ['bank', 'cash'])]
    )
    
    account_move_id = fields.Many2one(
        'account.move',
        string='Asiento Contable',
        readonly=True,
        copy=False
    )
    
    reference = fields.Char(
        string='Referencia',
        help='Referencia del pago (número de transacción, etc.)'
    )
    
    is_applied = fields.Boolean(
        string='Aplicado',
        default=False,
        readonly=True,
        help='Indica si el pago ya fue aplicado al checkout'
    )
    
    # Campos relacionados
    currency_id = fields.Many2one(
        related='reservation_id.currency_id',
        string='Moneda',
        readonly=True,
        store=True
    )
    
    company_id = fields.Many2one(
        related='reservation_id.company_id',
        string='Compañía',
        readonly=True,
        store=True
    )
    
    partner_id = fields.Many2one(
        related='reservation_id.partner_id',
        string='Cliente',
        readonly=True,
        store=True
    )
    
    state = fields.Selection(
        related='reservation_id.state',
        string='Estado Reserva',
        readonly=True,
        store=True
    )
    
    room_number = fields.Char(
        related='reservation_id.room_number',
        string='Habitación',
        readonly=True,
        store=True
    )
    
    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('El monto del pago debe ser mayor a cero'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para validar y crear asiento contable"""
        payments = super().create(vals_list)
        for payment in payments:
            # Validar estado de la reserva
            if payment.reservation_id.state not in ['confirmed', 'checked_in']:
                raise ValidationError(
                    _('Solo se pueden registrar anticipos en reservas confirmadas o en casa')
                )
            
            # Crear asiento contable
            payment.create_account_move()
            
            # Notificar
            payment.reservation_id.message_post(
                body=_('Anticipo registrado: %s %s') % (
                    payment.amount,
                    payment.currency_id.symbol
                )
            )
        
        return payments
    
    def create_account_move(self):
        """Crea el asiento contable del anticipo"""
        self.ensure_one()
        
        if self.account_move_id:
            raise UserError(_('Este pago ya tiene un asiento contable'))
        
        # Obtener cuentas
        debit_account = self.journal_id.default_account_id
        if not debit_account:
            raise UserError(
                _('El diario %s no tiene cuenta contable configurada') % self.journal_id.name
            )
        
        # Cuenta de anticipos de clientes
        # Usar cuenta por cobrar del cliente o cuenta de ingresos diferidos
        credit_account = self.partner_id.property_account_receivable_id
        
        if not credit_account:
            raise UserError(_('No se encontró cuenta contable para el anticipo'))
        
        # Crear asiento
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.payment_date.date() if self.payment_date else fields.Date.today(),
            'ref': _('Anticipo Reserva %s - Hab. %s') % (
                self.reservation_id.name,
                self.room_number
            ),
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'line_ids': [
                (0, 0, {
                    'name': _('Anticipo - %s') % self.name,
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                }),
                (0, 0, {
                    'name': _('Anticipo - %s') % self.name,
                    'account_id': credit_account.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                })
            ]
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        self.account_move_id = move
        
        return move
    
    def action_view_account_move(self):
        """Abre el asiento contable relacionado"""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('Este pago no tiene asiento contable'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asiento Contable'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def unlink(self):
        """Override unlink para validar y revertir asiento"""
        for payment in self:
            if payment.is_applied:
                raise UserError(_('No se puede eliminar un anticipo ya aplicado'))
            
            if payment.reservation_id.state not in ['confirmed', 'checked_in']:
                raise UserError(
                    _('No se pueden eliminar anticipos de una reserva en estado %s') % 
                    payment.reservation_id.state
                )
            
            # Revertir asiento contable si existe
            if payment.account_move_id:
                if payment.account_move_id.state == 'posted':
                    payment.account_move_id.button_cancel()
                payment.account_move_id.unlink()
        
        return super().unlink()
    
    @api.onchange('payment_method_id')
    def _onchange_payment_method_id(self):
        """Actualiza el diario basado en el método de pago"""
        if self.payment_method_id:
            # Buscar diario asociado al método de pago
            if self.payment_method_id.journal_id:
                self.journal_id = self.payment_method_id.journal_id
            else:
                # Buscar diario por tipo
                if self.payment_method_id.type == 'cash':
                    journal = self.env['account.journal'].search([
                        ('type', '=', 'cash'),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                else:
                    journal = self.env['account.journal'].search([
                        ('type', '=', 'bank'),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                
                if journal:
                    self.journal_id = journal