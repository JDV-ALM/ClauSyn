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
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
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
        copy=False,
        ondelete='restrict',
        help='Asiento contable del anticipo'
    )
    
    reference = fields.Char(
        string='Referencia',
        help='Referencia del pago (número de transacción, etc.)'
    )
    
    is_applied = fields.Boolean(
        string='Aplicado',
        default=False,
        readonly=True,
        help='Indica si el anticipo ya fue aplicado al checkout'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )
    
    partner_id = fields.Many2one(
        related='reservation_id.partner_id',
        string='Cliente',
        store=True,
        readonly=True
    )
    
    room_number = fields.Char(
        related='reservation_id.room_number',
        string='Habitación',
        store=True,
        readonly=True
    )
    
    state = fields.Selection(
        related='reservation_id.state',
        string='Estado Reserva',
        store=True
    )
    
    # Campo para compatibilidad con compute de totales en reservation
    amount_reservation_currency = fields.Monetary(
        string='Monto en Moneda de Reserva',
        compute='_compute_amount_reservation_currency',
        currency_field='reservation_currency_id',
        store=True,
        help='Monto del anticipo convertido a la moneda de la reserva'
    )
    
    reservation_currency_id = fields.Many2one(
        'res.currency',
        related='reservation_id.currency_id',
        string='Moneda de Reserva',
        store=True,
        readonly=True
    )

    # Campos para moneda alternativa del hotel
    alternative_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Alternativa',
        related='company_id.alternative_hotel_currency_id',
        store=True,
        readonly=True,
        help='Moneda de referencia del hotel para economías inflacionarias'
    )

    amount_alt = fields.Monetary(
        string='Monto (Moneda Alt)',
        compute='_compute_amount_alternative',
        store=True,
        currency_field='alternative_currency_id',
        help='Monto del pago convertido a la moneda alternativa del hotel al tipo de cambio del momento del pago'
    )

    exchange_rate_at_payment = fields.Float(
        string='Tasa de Cambio',
        compute='_compute_amount_alternative',
        store=True,
        digits=(12, 6),
        help='Tasa de cambio usada para convertir a moneda alternativa'
    )

    @api.depends('amount', 'currency_id', 'reservation_currency_id', 'payment_date')
    def _compute_amount_reservation_currency(self):
        """Calcula el monto en la moneda de la reserva"""
        for payment in self:
            if payment.currency_id and payment.reservation_currency_id:
                if payment.currency_id == payment.reservation_currency_id:
                    payment.amount_reservation_currency = payment.amount
                else:
                    # Convertir a la moneda de la reserva
                    payment.amount_reservation_currency = payment.currency_id._convert(
                        payment.amount,
                        payment.reservation_currency_id,
                        payment.company_id,
                        payment.payment_date or fields.Date.today()
                    )
            else:
                payment.amount_reservation_currency = payment.amount

    @api.depends('amount', 'currency_id', 'alternative_currency_id', 'payment_date')
    def _compute_amount_alternative(self):
        """Calcula el monto en moneda alternativa del hotel"""
        for payment in self:
            # Si no hay moneda alternativa configurada, usar valores en cero
            if not payment.alternative_currency_id:
                payment.amount_alt = 0.0
                payment.exchange_rate_at_payment = 0.0
                continue

            # Si la moneda del pago es la misma que la alternativa, no hay conversión
            if payment.currency_id == payment.alternative_currency_id:
                payment.amount_alt = payment.amount
                payment.exchange_rate_at_payment = 1.0
            else:
                # Convertir a moneda alternativa
                payment_date = payment.payment_date.date() if payment.payment_date else fields.Date.today()

                # Calcular tasa de cambio
                payment.exchange_rate_at_payment = payment.currency_id._get_conversion_rate(
                    payment.currency_id,
                    payment.alternative_currency_id,
                    payment.company_id,
                    payment_date
                )

                # Convertir monto
                payment.amount_alt = payment.currency_id._convert(
                    payment.amount,
                    payment.alternative_currency_id,
                    payment.company_id,
                    payment_date
                )

    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('El monto del anticipo debe ser mayor a cero'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para crear automáticamente el asiento contable"""
        payments = super().create(vals_list)

        for payment in payments:
            # Crear el asiento contable automáticamente
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
        """Crea el asiento contable del anticipo directamente"""
        self.ensure_one()

        if self.account_move_id:
            raise UserError(_('Este anticipo ya tiene un asiento contable asociado'))

        # Validar que la cuenta de anticipos esté configurada
        if not self.company_id.hotel_advance_account_id:
            raise UserError(_(
                'No se ha configurado la cuenta de anticipos de hotel. '
                'Por favor vaya a Configuración > Hotel y configure la cuenta de anticipos.'
            ))

        # Obtener cuentas
        advance_account = self.company_id.hotel_advance_account_id
        liquidity_account = self.journal_id.default_account_id

        if not liquidity_account:
            raise UserError(_(
                'El diario "%s" no tiene una cuenta por defecto configurada.'
            ) % self.journal_id.name)

        # Preparar referencia
        ref_text = _('Anticipo - Reserva %s - Hab. %s') % (
            self.reservation_id.name,
            self.room_number
        )
        if self.reference:
            ref_text += _(' - Ref: %s') % self.reference

        # Preparar líneas del asiento
        line_vals = []

        # Línea 1: DÉBITO en cuenta de liquidez (banco/caja)
        line_vals.append((0, 0, {
            'name': ref_text,
            'account_id': liquidity_account.id,
            'partner_id': self.partner_id.id,
            'debit': self.amount,
            'credit': 0.0,
            'currency_id': self.currency_id.id if self.currency_id != self.company_id.currency_id else False,
            'amount_currency': self.amount if self.currency_id != self.company_id.currency_id else 0.0,
        }))

        # Línea 2: CRÉDITO en cuenta de anticipos
        line_vals.append((0, 0, {
            'name': ref_text,
            'account_id': advance_account.id,
            'partner_id': self.partner_id.id,
            'debit': 0.0,
            'credit': self.amount,
            'currency_id': self.currency_id.id if self.currency_id != self.company_id.currency_id else False,
            'amount_currency': -self.amount if self.currency_id != self.company_id.currency_id else 0.0,
        }))

        # Crear el asiento
        move_vals = {
            'move_type': 'entry',
            'date': self.payment_date.date() if self.payment_date else fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': ref_text,
            'line_ids': line_vals,
        }

        account_move = self.env['account.move'].create(move_vals)

        # Publicar el asiento
        account_move.action_post()

        # Vincular el asiento con este anticipo
        self.account_move_id = account_move

        return account_move
    
    def action_view_account_move(self):
        """Abre el asiento contable relacionado"""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('Este anticipo no tiene asiento contable'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Asiento Contable'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def unlink(self):
        """Override unlink para validar y cancelar asiento"""
        for payment in self:
            if payment.is_applied:
                raise UserError(_('No se puede eliminar un anticipo ya aplicado'))

            if payment.reservation_id.state not in ['confirmed', 'checked_in']:
                raise UserError(
                    _('No se pueden eliminar anticipos de una reserva en estado %s') %
                    payment.reservation_id.state
                )

            # Cancelar y eliminar el asiento contable si existe
            if payment.account_move_id:
                # Si el asiento está publicado, primero lo cancelamos
                if payment.account_move_id.state == 'posted':
                    payment.account_move_id.button_draft()
                # Si el asiento está conciliado, no permitir eliminar
                if payment.account_move_id.line_ids.filtered(lambda l: l.reconciled):
                    raise UserError(_('No se puede eliminar un anticipo con asiento conciliado'))
                # Eliminar el asiento
                payment.account_move_id.unlink()

        return super().unlink()

    def action_apply_to_checkout(self):
        """Marca el anticipo como aplicado (será usado en el checkout)"""
        self.ensure_one()
        if self.is_applied:
            raise UserError(_('Este anticipo ya está aplicado'))
        
        self.is_applied = True
        
        # Mensaje en el chatter
        self.reservation_id.message_post(
            body=_('Anticipo aplicado al checkout: %s %s') % (
                self.amount,
                self.currency_id.symbol
            )
        )
        
        return True