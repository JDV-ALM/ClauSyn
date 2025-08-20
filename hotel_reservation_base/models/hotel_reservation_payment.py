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
    
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Pago Contable',
        readonly=True,
        copy=False,
        ondelete='restrict'
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
        """Crea el account.payment del anticipo"""
        self.ensure_one()
        
        if self.account_payment_id:
            raise UserError(_('Este anticipo ya tiene un pago contable asociado'))
        
        # Determinar tipo de pago y cuenta destino
        payment_type = 'inbound'  # Recibimos dinero del cliente
        partner_type = 'customer'
        
        # Obtener la cuenta de destino (cuenta por cobrar del cliente)
        if self.partner_id:
            destination_account = self.partner_id.with_company(self.company_id).property_account_receivable_id
        else:
            destination_account = self.env['account.account'].search([
                ('company_id', '=', self.company_id.id),
                ('account_type', '=', 'asset_receivable'),
                ('deprecated', '=', False),
            ], limit=1)
        
        if not destination_account:
            raise UserError(_('No se encontró cuenta por cobrar para el cliente'))
        
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
            })
        
        # Preparar valores del payment
        payment_vals = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.payment_date.date() if self.payment_date else fields.Date.today(),
            'journal_id': self.journal_id.id,
            'payment_method_line_id': payment_method_line.id,
            'destination_account_id': destination_account.id,
            'ref': _('Anticipo - Reserva %s - Hab. %s') % (
                self.reservation_id.name,
                self.room_number
            ),
            'payment_reference': self.reference or '',
        }
        
        # Crear el payment
        account_payment = self.env['account.payment'].create(payment_vals)
        
        # Publicar el payment (esto crea el asiento contable)
        # El payment queda publicado pero NO conciliado
        account_payment.action_post()
        
        # Vincular el payment con este anticipo
        self.account_payment_id = account_payment
        
        return account_payment
    
    def action_view_account_payment(self):
        """Abre el account.payment relacionado"""
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
        """Override unlink para validar y cancelar payment"""
        for payment in self:
            if payment.is_applied:
                raise UserError(_('No se puede eliminar un anticipo ya aplicado'))
            
            if payment.reservation_id.state not in ['confirmed', 'checked_in']:
                raise UserError(
                    _('No se pueden eliminar anticipos de una reserva en estado %s') % 
                    payment.reservation_id.state
                )
            
            # Cancelar y eliminar el account.payment si existe
            if payment.account_payment_id:
                # Si el payment está publicado, primero lo cancelamos
                if payment.account_payment_id.state == 'posted':
                    payment.account_payment_id.action_cancel()
                # Si el payment está conciliado, no permitir eliminar
                if payment.account_payment_id.is_reconciled:
                    raise UserError(_('No se puede eliminar un anticipo con pago conciliado'))
                # Eliminar el payment
                payment.account_payment_id.unlink()
        
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