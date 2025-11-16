# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'

    hotel_reservation_id = fields.Many2one(
        'hotel.reservation',
        string='Reserva de Hotel',
        help='Reserva hotelera asociada a esta orden',
        index=True,
        ondelete='restrict'
    )
