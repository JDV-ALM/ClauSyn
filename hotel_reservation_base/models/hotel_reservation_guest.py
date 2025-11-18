# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HotelReservationGuest(models.Model):
    _name = 'hotel.reservation.guest'
    _description = 'Huésped de Reserva'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de los huéspedes'
    )

    reservation_id = fields.Many2one(
        'hotel.reservation',
        string='Reserva',
        required=True,
        ondelete='cascade',
        index=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        required=True,
        help='Contacto del huésped'
    )

    room_number = fields.Char(
        string='Número/Nombre de Habitación',
        help='Habitación asignada a este huésped'
    )

    adults = fields.Integer(
        string='Adultos',
        default=1,
        help='Número de adultos en esta habitación'
    )

    children = fields.Integer(
        string='Niños',
        default=0,
        help='Número de niños en esta habitación'
    )

    checkin_date = fields.Datetime(
        string='Check-in Previsto',
        help='Fecha y hora prevista de check-in para este huésped'
    )

    checkout_date = fields.Datetime(
        string='Check-out Previsto',
        help='Fecha y hora prevista de check-out para este huésped'
    )

    # Campos relacionados
    state = fields.Selection(
        related='reservation_id.state',
        string='Estado Reserva',
        readonly=True,
        store=True
    )

    company_id = fields.Many2one(
        related='reservation_id.company_id',
        string='Compañía',
        readonly=True,
        store=True
    )

    is_locked = fields.Boolean(
        related='reservation_id.is_locked',
        string='Bloqueado',
        readonly=True,
        store=True
    )

    notes = fields.Text(
        string='Notas',
        help='Notas específicas sobre este huésped'
    )

    @api.constrains('adults')
    def _check_adults(self):
        for guest in self:
            if guest.adults < 0:
                raise ValidationError(_('El número de adultos no puede ser negativo'))

    @api.constrains('children')
    def _check_children(self):
        for guest in self:
            if guest.children < 0:
                raise ValidationError(_('El número de niños no puede ser negativo'))

    @api.constrains('checkin_date', 'checkout_date')
    def _check_dates(self):
        for guest in self:
            if guest.checkin_date and guest.checkout_date:
                if guest.checkin_date >= guest.checkout_date:
                    raise ValidationError(_('La fecha de checkout debe ser posterior al check-in'))

    def name_get(self):
        result = []
        for guest in self:
            name = guest.partner_id.name
            if guest.room_number:
                name = f"{name} - {guest.room_number}"
            result.append((guest.id, name))
        return result
