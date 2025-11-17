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

    account_payment_id = fields.Many2one(
        'account.payment',
        string='Pago Contable',
        readonly=True,
        copy=False,
        ondelete='restrict',
        help='Pago contable que genera el asiento del anticipo'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Registrado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', required=True, readonly=True, tracking=True)
    
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
    
    reservation_state = fields.Selection(
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
        """Override create para crear automáticamente el account.payment"""
        payments = super().create(vals_list)

        for payment in payments:
            # Crear el account.payment automáticamente
            payment.create_account_payment()

            # Notificar
            payment.reservation_id.message_post(
                body=_('Anticipo registrado: %s %s') % (
                    payment.amount,
                    payment.currency_id.symbol
                )
            )

        return payments
    
    def create_account_payment(self):
        """Crea el account.payment del anticipo (usará cuenta de anticipos)"""
        self.ensure_one()

        if self.account_payment_id:
            raise UserError(_('Este anticipo ya tiene un pago contable asociado'))

        # Validar que la cuenta de anticipos esté configurada
        if not self.company_id.hotel_advance_account_id:
            raise UserError(_(
                'No se ha configurado la cuenta de anticipos de hotel. '
                'Por favor vaya a Configuración > Hotel y configure la cuenta de anticipos.'
            ))

        # Determinar tipo de pago
        payment_type = 'inbound'  # Recibimos dinero del cliente
        partner_type = 'customer'

        # Buscar método de pago en account.payment.method
        payment_method = self.env['account.payment.method'].search([
            ('payment_type', '=', payment_type),
            ('code', '=', 'manual'),  # Método manual por defecto
        ], limit=1)

        if not payment_method:
            raise UserError(_('No se encontró método de pago manual'))

        # Buscar o crear la línea del método de pago
        payment_method_line = self.env['account.payment.method.line'].search([
            ('payment_method_id', '=', payment_method.id),
            ('journal_id', '=', self.journal_id.id),
        ], limit=1)

        if not payment_method_line:
            # Crear la línea del método de pago si no existe
            payment_method_line = self.env['account.payment.method.line'].create({
                'payment_method_id': payment_method.id,
                'journal_id': self.journal_id.id,
                'name': payment_method.name,
            })

        # Preparar referencia
        ref_text = _('Anticipo - Reserva %s - Hab. %s') % (
            self.reservation_id.name,
            self.room_number
        )
        if self.reference:
            ref_text += _(' - Ref: %s') % self.reference

        # Preparar valores del payment
        # El override en account_payment.py reemplazará la cuenta receivable con la cuenta de anticipos
        payment_vals = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.payment_date.date() if self.payment_date else fields.Date.today(),
            'journal_id': self.journal_id.id,
            'payment_method_line_id': payment_method_line.id,
            'ref': ref_text,
            # Campos específicos para anticipos de hotel (definidos en account_payment.py)
            'is_hotel_advance': True,
            'hotel_reservation_payment_id': self.id,
        }

        # Crear el payment (en borrador)
        account_payment = self.env['account.payment'].sudo().create(payment_vals)

        # Publicar el payment (esto crea el asiento contable)
        # El payment crea el asiento con cuenta outstanding y cuenta de anticipos
        account_payment.action_post()

        # Vincular el payment con este anticipo
        self.account_payment_id = account_payment
        self.state = 'posted'

        return account_payment
    
    def action_view_account_payment(self):
        """Abre el pago contable relacionado"""
        self.ensure_one()
        if not self.account_payment_id:
            raise UserError(_('Este anticipo no tiene pago contable'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago Contable'),
            'res_model': 'account.payment',
            'res_id': self.account_payment_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def unlink(self):
        """Override unlink para validar - solo se permiten eliminar anticipos en borrador"""
        for payment in self:
            # Solo permitir eliminar anticipos en estado borrador
            if payment.state != 'draft':
                raise UserError(_(
                    'No se puede eliminar un anticipo en estado %s. '
                    'Use el botón "Cancelar" en su lugar.'
                ) % payment.state)

            if payment.is_applied:
                raise UserError(_('No se puede eliminar un anticipo ya aplicado'))

            # Si existe account.payment, eliminarlo también
            if payment.account_payment_id:
                # Validar que no esté conciliado
                if payment.account_payment_id.move_id:
                    if payment.account_payment_id.move_id.line_ids.filtered(lambda l: l.reconciled):
                        raise UserError(_('No se puede eliminar un anticipo con pago conciliado'))
                    # Cancelar y eliminar el pago
                    if payment.account_payment_id.state == 'posted':
                        payment.account_payment_id.button_draft()
                    payment.account_payment_id.unlink()

        return super().unlink()

    def action_cancel(self):
        """Cancela el anticipo y su pago contable asociado"""
        for payment in self:
            if payment.state == 'cancel':
                raise UserError(_('Este anticipo ya está cancelado'))

            if payment.is_applied:
                raise UserError(_('No se puede cancelar un anticipo ya aplicado al checkout'))

            # Cancelar el account.payment si existe
            if payment.account_payment_id:
                if payment.account_payment_id.state == 'posted':
                    # Validar que no esté conciliado
                    if payment.account_payment_id.move_id.line_ids.filtered(lambda l: l.reconciled):
                        raise UserError(_(
                            'No se puede cancelar un anticipo con pago conciliado. '
                            'Primero debe desconciliar el pago en el banco.'
                        ))
                    # Cancelar el pago (esto cancela el asiento)
                    payment.account_payment_id.action_cancel()

            # Actualizar estado del anticipo
            payment.state = 'cancel'

            # Mensaje en el chatter
            payment.reservation_id.message_post(
                body=_('Anticipo cancelado: %s %s') % (
                    payment.amount,
                    payment.currency_id.symbol
                )
            )

        return True

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