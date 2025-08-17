# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HotelPaymentWizard(models.TransientModel):
    _name = 'hotel.payment.wizard'
    _description = 'Wizard para Registrar Anticipo'
    
    reservation_id = fields.Many2one(
        'hotel.reservation',
        string='Reserva',
        required=True,
        readonly=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        readonly=True
    )
    
    room_number = fields.Char(
        string='Habitación',
        related='reservation_id.room_number',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='reservation_id.currency_id',
        readonly=True
    )
    
    balance = fields.Monetary(
        string='Saldo Actual',
        related='reservation_id.balance',
        readonly=True,
        currency_field='currency_id'
    )
    
    amount = fields.Monetary(
        string='Monto a Pagar',
        required=True,
        currency_field='currency_id'
    )
    
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de Pago',
        required=True,
        domain=[('active', '=', True)]
    )
    
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain=[('type', 'in', ['bank', 'cash'])]
    )
    
    payment_date = fields.Datetime(
        string='Fecha de Pago',
        required=True,
        default=fields.Datetime.now
    )
    
    reference = fields.Char(
        string='Referencia',
        help='Número de transacción, cheque, etc.'
    )
    
    memo = fields.Char(
        string='Memo',
        default='Anticipo'
    )
    
    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero'))
    
    @api.onchange('payment_method_id')
    def _onchange_payment_method_id(self):
        """Actualiza el diario basado en el método de pago"""
        if self.payment_method_id:
            # Buscar diario asociado al método de pago
            if self.payment_method_id.journal_id:
                self.journal_id = self.payment_method_id.journal_id
            else:
                # Buscar diario por tipo
                company_id = self.reservation_id.company_id
                if self.payment_method_id.type == 'cash':
                    journal = self.env['account.journal'].search([
                        ('type', '=', 'cash'),
                        ('company_id', '=', company_id.id)
                    ], limit=1)
                else:
                    journal = self.env['account.journal'].search([
                        ('type', '=', 'bank'),
                        ('company_id', '=', company_id.id)
                    ], limit=1)
                
                if journal:
                    self.journal_id = journal
    
    def action_create_payment(self):
        """Crea el registro de pago"""
        self.ensure_one()
        
        # Validar estado de la reserva
        if self.reservation_id.state not in ['confirmed', 'checked_in']:
            raise UserError(
                _('Solo se pueden registrar anticipos en reservas confirmadas o en casa')
            )
        
        # Crear el pago
        payment_vals = {
            'reservation_id': self.reservation_id.id,
            'name': self.memo,
            'amount': self.amount,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
            'reference': self.reference,
        }
        
        payment = self.env['hotel.reservation.payment'].create(payment_vals)
        
        # Mensaje de confirmación
        message = _('Anticipo registrado exitosamente: %s %s') % (
            self.amount,
            self.currency_id.symbol
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': message,
                'next': {
                    'type': 'ir.actions.act_window_close'
                },
            }
        }