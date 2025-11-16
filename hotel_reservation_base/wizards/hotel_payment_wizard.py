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
    
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain=[('type', 'in', ['bank', 'cash'])]
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='journal_id.currency_id',
        readonly=True
    )

    reservation_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Reserva',
        related='reservation_id.currency_id',
        readonly=True
    )
    
    balance = fields.Monetary(
        string='Saldo Actual',
        related='reservation_id.balance',
        readonly=True,
        currency_field='reservation_currency_id'
    )
    
    amount = fields.Monetary(
        string='Monto a Pagar',
        required=True,
        currency_field='currency_id'
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

    def action_create_payment(self):
        """Crea el registro de pago con account.payment"""
        self.ensure_one()
        
        # Validar estado de la reserva
        if self.reservation_id.state not in ['confirmed', 'checked_in']:
            raise UserError(
                _('Solo se pueden registrar anticipos en reservas confirmadas o en casa')
            )
        
        # Asegurar que journal_id esté configurado
        if not self.journal_id:
            raise UserError(_('Debe seleccionar un diario para el pago'))

        # Obtener moneda del diario o usar la de la compañía
        currency_id = self.journal_id.currency_id.id if self.journal_id.currency_id else self.env.company.currency_id.id

        # Crear el anticipo en hotel.reservation.payment
        # Este modelo creará automáticamente el account.payment
        payment_vals = {
            'reservation_id': self.reservation_id.id,
            'name': self.memo,
            'amount': self.amount,
            'currency_id': currency_id,
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
            'reference': self.reference,
        }
        
        # Crear el pago - esto automáticamente creará el account.payment
        payment = self.env['hotel.reservation.payment'].create(payment_vals)

        # Obtener moneda para mensaje
        currency = self.env['res.currency'].browse(currency_id)

        # Mensaje de confirmación con información del payment creado
        if payment.account_payment_id:
            message = _('Anticipo registrado exitosamente: %s %s\nPago contable #%s creado y publicado') % (
                self.amount,
                currency.symbol,
                payment.account_payment_id.name
            )
        else:
            message = _('Anticipo registrado exitosamente: %s %s') % (
                self.amount,
                currency.symbol
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Anticipo Registrado'),
                'message': message,
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                },
            }
        }