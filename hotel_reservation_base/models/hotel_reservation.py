# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class HotelReservation(models.Model):
    _name = 'hotel.reservation'
    _description = 'Reserva de Hotel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkin_date desc, id desc'
    
    name = fields.Char(
        string='Código',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        help='Cliente de la reserva'
    )
    
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de Precios',
        required=True,
        tracking=True,
        help='Lista de precios para esta reserva'
    )
    
    room_number = fields.Char(
        string='Habitación',
        required=True,
        tracking=True,
        help='Identificador de habitación'
    )
    
    checkin_date = fields.Datetime(
        string='Check-in Previsto',
        required=True,
        tracking=True,
        default=fields.Datetime.now
    )
    
    checkin_real = fields.Datetime(
        string='Check-in Real',
        tracking=True,
        help='Fecha y hora real de entrada'
    )
    
    checkout_date = fields.Datetime(
        string='Check-out Previsto',
        required=True,
        tracking=True
    )
    
    checkout_real = fields.Datetime(
        string='Check-out Real',
        tracking=True,
        help='Fecha y hora real de salida'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('checked_in', 'En Casa'),
        ('checked_out', 'Checkout Realizado'),
        ('done', 'Facturada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True, copy=False)
    
    # Relaciones
    line_ids = fields.One2many(
        'hotel.reservation.line',
        'reservation_id',
        string='Cargos Manuales',
        copy=False
    )
    
    payment_ids = fields.One2many(
        'hotel.reservation.payment',
        'reservation_id',
        string='Anticipos',
        copy=False
    )
    
    # Este campo se habilitará cuando se instale pos_hotel_integration
    # pos_order_ids = fields.One2many(
    #     'pos.order',
    #     'hotel_reservation_id',
    #     string='Órdenes POS',
    #     copy=False,
    #     readonly=True
    # )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True,
        copy=False,
        help='Orden de venta generada en el checkout'
    )
    
    # Campos monetarios
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self._get_default_currency(),
        help='Moneda base de la reserva (típicamente USD)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )
    
    amount_total = fields.Monetary(
        string='Total Consumos',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Total de consumos en la moneda de la reserva'
    )
    
    amount_paid = fields.Monetary(
        string='Total Anticipos',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Total de anticipos convertidos a la moneda de la reserva'
    )
    
    balance = fields.Monetary(
        string='Saldo Pendiente',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Saldo pendiente en la moneda de la reserva'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Observaciones internas'
    )
    
    def _get_default_currency(self):
        """Obtiene la moneda por defecto (USD si existe, sino la de la compañía)"""
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        return usd if usd else self.env.company.currency_id
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Actualiza la lista de precios basada en el cliente"""
        if self.partner_id:
            # Si el cliente tiene una lista de precios específica
            if self.partner_id.property_product_pricelist:
                self.pricelist_id = self.partner_id.property_product_pricelist
            else:
                # Buscar lista de precios por defecto en la moneda de la reserva
                pricelist = self.env['product.pricelist'].search([
                    ('currency_id', '=', self.currency_id.id),
                    ('active', '=', True)
                ], limit=1)
                if pricelist:
                    self.pricelist_id = pricelist
    
    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        """Actualiza la moneda basada en la lista de precios"""
        if self.pricelist_id:
            self.currency_id = self.pricelist_id.currency_id
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hotel.reservation') or _('New')
        return super().create(vals_list)
    
    @api.depends('line_ids.price_total', 'payment_ids.amount_reservation_currency')
    def _compute_totals(self):
        for reservation in self:
            # Total de cargos manuales
            manual_charges = sum(reservation.line_ids.mapped('price_total'))
            
            # Total de órdenes POS se calculará cuando se instale pos_hotel_integration
            pos_charges = 0
            # if hasattr(reservation, 'pos_order_ids'):
            #     pos_charges = sum(reservation.pos_order_ids.filtered(
            #         lambda o: o.paid_later
            #     ).mapped('amount_total'))
            
            # Total de anticipos (convertidos a la moneda de la reserva)
            total_payments = sum(reservation.payment_ids.mapped('amount_reservation_currency'))
            
            reservation.amount_total = manual_charges + pos_charges
            reservation.amount_paid = total_payments
            reservation.balance = reservation.amount_total - reservation.amount_paid
    
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
    
    def action_checkin(self):
        """Registra entrada del huésped"""
        for reservation in self:
            if reservation.state != 'confirmed':
                raise UserError(_('Solo se puede hacer checkin de reservas confirmadas'))
            
            reservation.write({
                'state': 'checked_in',
                'checkin_real': fields.Datetime.now()
            })
            reservation.message_post(body=_('Check-in realizado'))
    
    def action_checkout(self):
        """Inicia proceso de checkout"""
        for reservation in self:
            if reservation.state != 'checked_in':
                raise UserError(_('Solo se puede hacer checkout de reservas en casa'))
            
            reservation.write({
                'state': 'checked_out',
                'checkout_real': fields.Datetime.now()
            })
            reservation.message_post(body=_('Checkout realizado'))
            
            # Aquí se llamará al wizard de checkout en el módulo hotel_sale_bridge
            # Por ahora solo cambiamos el estado
    
    def action_done(self):
        """Marca como facturada"""
        for reservation in self:
            if reservation.state != 'checked_out':
                raise UserError(_('Solo se pueden marcar como facturadas las reservas con checkout'))
            
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
    
    # def action_view_pos_orders(self):
    #     """Abre vista de órdenes POS relacionadas"""
    #     """Se habilitará cuando se instale pos_hotel_integration"""
    #     self.ensure_one()
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('Órdenes POS'),
    #         'res_model': 'pos.order',
    #         'view_mode': 'tree,form',
    #         'domain': [('hotel_reservation_id', '=', self.id)],
    #         'context': {'default_hotel_reservation_id': self.id}
    #     }
    
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