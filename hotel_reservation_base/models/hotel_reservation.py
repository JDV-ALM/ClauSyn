# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class HotelReservation(models.Model):
    _name = 'hotel.reservation'
    _description = 'Reserva de Hotel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkin_date desc, id desc'
    
    name = fields.Char(
        string='Número de Reserva',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        help='Cliente responsable de la reserva'
    )
    
    room_id = fields.Many2one(
        'product.product',
        string='Habitación',
        domain=[('is_room', '=', True)],
        help='Producto configurado como habitación'
    )
    
    room_number = fields.Char(
        string='Número/Nombre de Habitación',
        required=True,
        tracking=True,
        help='Identificador físico de la habitación'
    )
    
    room_type_id = fields.Many2one(
        'product.category',
        string='Tipo de Habitación',
        compute='_compute_room_type',
        store=True
    )
    
    checkin_date = fields.Datetime(
        string='Check-in Previsto',
        required=True,
        tracking=True,
        default=lambda self: fields.Datetime.now()
    )
    
    checkout_date = fields.Datetime(
        string='Check-out Previsto',
        required=True,
        tracking=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=1)
    )
    
    checkin_real = fields.Datetime(
        string='Check-in Real',
        readonly=True,
        tracking=True
    )
    
    checkout_real = fields.Datetime(
        string='Check-out Real',
        readonly=True,
        tracking=True
    )
    
    adults = fields.Integer(
        string='Adultos',
        default=1,
        required=True
    )
    
    children = fields.Integer(
        string='Niños',
        default=0
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('checked_in', 'En Casa'),
        ('checked_out', 'Check-out'),
        ('done', 'Facturada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True, required=True)
    
    # Relaciones con otros modelos
    line_ids = fields.One2many(
        'hotel.reservation.line',
        'reservation_id',
        string='Cargos Manuales'
    )
    
    payment_ids = fields.One2many(
        'hotel.reservation.payment',
        'reservation_id',
        string='Anticipos'
    )
    
    pos_order_ids = fields.One2many(
        'pos.order',
        'hotel_reservation_id',
        string='Órdenes POS',
        domain=[('state', 'in', ['paid', 'done', 'invoiced'])]
    )
    
    pos_order_count = fields.Integer(
        string='Número de Órdenes POS',
        compute='_compute_pos_order_count'
    )
    
    # Campos monetarios
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    room_subtotal = fields.Monetary(
        string='Subtotal Habitación',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    
    charges_subtotal = fields.Monetary(
        string='Subtotal Cargos Manuales',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    
    pos_charges_subtotal = fields.Monetary(
        string='Subtotal Consumos POS',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        tracking=True
    )
    
    total_paid = fields.Monetary(
        string='Total Pagado',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    
    balance = fields.Monetary(
        string='Saldo',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    
    # Otros campos
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas internas sobre la reserva'
    )
    
    # Métodos de cálculo
    @api.depends('room_id')
    def _compute_room_type(self):
        for reservation in self:
            if reservation.room_id:
                reservation.room_type_id = reservation.room_id.categ_id
            else:
                reservation.room_type_id = False
    
    @api.depends('pos_order_ids')
    def _compute_pos_order_count(self):
        for reservation in self:
            reservation.pos_order_count = len(reservation.pos_order_ids)
    
    @api.depends('line_ids.subtotal', 'payment_ids.amount', 
                 'pos_order_ids.amount_total', 'room_id', 
                 'checkin_date', 'checkout_date')
    def _compute_amounts(self):
        for reservation in self:
            # Calcular noches
            if reservation.checkin_date and reservation.checkout_date:
                delta = reservation.checkout_date - reservation.checkin_date
                nights = delta.days
            else:
                nights = 0
            
            # Subtotal habitación
            if reservation.room_id and nights > 0:
                reservation.room_subtotal = reservation.room_id.list_price * nights
            else:
                reservation.room_subtotal = 0.0
            
            # Subtotal cargos manuales
            reservation.charges_subtotal = sum(line.subtotal for line in reservation.line_ids)
            
            # Subtotal órdenes POS
            reservation.pos_charges_subtotal = sum(
                order.amount_total for order in reservation.pos_order_ids
                if order.state in ['paid', 'done', 'invoiced']
            )
            
            # Total general
            reservation.amount_total = (
                reservation.room_subtotal + 
                reservation.charges_subtotal + 
                reservation.pos_charges_subtotal
            )
            
            # Total pagado (anticipos)
            reservation.total_paid = sum(
                payment.amount_reservation_currency for payment in reservation.payment_ids
            )
            
            # Saldo
            reservation.balance = reservation.amount_total - reservation.total_paid
    
    # Secuencia
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hotel.reservation') or _('New')
        return super().create(vals_list)
    
    # Métodos de acción - CORREGIDOS CON NOMBRES CORRECTOS
    def action_confirm(self):
        """Confirma la reserva"""
        for reservation in self:
            if reservation.state != 'draft':
                raise UserError(_('Solo se pueden confirmar reservas en borrador'))
            
            # Validaciones
            if reservation.checkin_date >= reservation.checkout_date:
                raise ValidationError(_('La fecha de checkout debe ser posterior al checkin'))
            
            reservation.state = 'confirmed'
            reservation.message_post(body=_('Reserva confirmada'))
    
    def action_check_in(self):
        """Registra entrada del huésped - NOMBRE CORREGIDO"""
        for reservation in self:
            if reservation.state != 'confirmed':
                raise UserError(_('Solo se puede hacer check-in de reservas confirmadas'))
            
            reservation.write({
                'state': 'checked_in',
                'checkin_real': fields.Datetime.now()
            })
            reservation.message_post(body=_('Check-in realizado'))
    
    def action_check_out(self):
        """Inicia proceso de checkout - NOMBRE CORREGIDO"""
        for reservation in self:
            if reservation.state != 'checked_in':
                raise UserError(_('Solo se puede hacer check-out de reservas en casa'))
            
            reservation.write({
                'state': 'checked_out',
                'checkout_real': fields.Datetime.now()
            })
            reservation.message_post(body=_('Check-out realizado'))
            
            # Aquí se llamará al wizard de checkout en el módulo hotel_sale_bridge
            # Por ahora solo cambiamos el estado
    
    def action_done(self):
        """Marca como facturada"""
        for reservation in self:
            if reservation.state != 'checked_out':
                raise UserError(_('Solo se pueden marcar como facturadas las reservas con check-out'))
            
            if reservation.balance > 0.01:  # Tolerancia de centavos
                raise UserError(_('No se puede cerrar una reserva con saldo pendiente'))
            
            reservation.state = 'done'
            reservation.message_post(body=_('Reserva facturada y cerrada'))
    
    def action_cancel(self):
        """Cancela la reserva"""
        for reservation in self:
            if reservation.state in ['done', 'cancelled']:
                raise UserError(_('No se puede cancelar una reserva facturada o ya cancelada'))
            
            # Verificar que no tenga movimientos
            if reservation.payment_ids:
                raise UserError(_('No se puede cancelar una reserva con pagos registrados'))
            
            reservation.state = 'cancelled'
            reservation.message_post(body=_('Reserva cancelada'))
    
    def action_view_pos_orders(self):
        """Abre vista de órdenes POS relacionadas"""
        # Se habilitará cuando se instale pos_hotel_integration
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Órdenes POS'),
            'res_model': 'pos.order',
            'view_mode': 'tree,form',
            'domain': [('hotel_reservation_id', '=', self.id)],
            'context': {'default_hotel_reservation_id': self.id}
        }
    
    def action_register_payment(self):
        """Abre wizard para registrar anticipo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Anticipo'),
            'res_model': 'hotel.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_reservation_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_amount': self.balance if self.balance > 0 else 0
            }
        }
    
    @api.constrains('checkin_date', 'checkout_date')
    def _check_dates(self):
        for reservation in self:
            if reservation.checkin_date and reservation.checkout_date:
                if reservation.checkin_date >= reservation.checkout_date:
                    raise ValidationError(_('La fecha de checkout debe ser posterior al checkin'))
    
    def unlink(self):
        for reservation in self:
            if reservation.state not in ['draft', 'cancelled']:
                raise UserError(_('Solo se pueden eliminar reservas en borrador o canceladas'))
        return super().unlink()