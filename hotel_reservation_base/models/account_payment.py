# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_hotel_advance = fields.Boolean(
        string='Es Anticipo de Hotel',
        default=False,
        help='Indica si este pago es un anticipo de reserva hotelera',
        readonly=True
    )

    hotel_reservation_payment_id = fields.Many2one(
        'hotel.reservation.payment',
        string='Anticipo de Reserva',
        readonly=True,
        ondelete='restrict'
    )

    @api.depends('is_hotel_advance', 'company_id')
    def _compute_destination_account_id(self):
        """Override para establecer cuenta de anticipos cuando aplique"""
        super()._compute_destination_account_id()

        for payment in self:
            if payment.is_hotel_advance and payment.company_id.hotel_advance_account_id:
                payment.destination_account_id = payment.company_id.hotel_advance_account_id

    def action_post(self):
        """Override para reemplazar cuenta receivable por anticipos DESPUÉS de crear el asiento"""
        # Primero ejecutar el action_post normal para crear el asiento
        result = super().action_post()

        # Luego modificar las líneas del asiento para anticipos de hotel
        for payment in self:
            if payment.is_hotel_advance and payment.move_id:
                advance_account = payment.company_id.hotel_advance_account_id

                if not advance_account:
                    raise UserError(_(
                        'No se ha configurado la cuenta de anticipos de hotel. '
                        'Por favor configure la cuenta en Configuración > Hotel > Cuenta de Anticipos'
                    ))

                # Buscar la línea del partner (receivable/payable) y reemplazarla con anticipos
                partner_receivable_account = payment.partner_id.property_account_receivable_id
                liquidity_account = payment.journal_id.default_account_id

                for line in payment.move_id.line_ids:
                    # Reemplazar la línea que NO es liquidity y tiene el partner
                    if line.account_id.id == partner_receivable_account.id:
                        # Cambiar la cuenta a anticipos
                        line.write({
                            'account_id': advance_account.id,
                            'name': _('Anticipo de Reserva - %s') % (
                                payment.hotel_reservation_payment_id.reservation_id.name
                                if payment.hotel_reservation_payment_id else payment.ref
                            )
                        })
                        break

        return result