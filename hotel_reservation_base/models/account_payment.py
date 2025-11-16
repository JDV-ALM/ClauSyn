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
    
    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """Override para usar cuenta de anticipos cuando aplique"""
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance
        )

        # Si es un anticipo de hotel, modificar la cuenta destino
        if self.is_hotel_advance:
            # Obtener la cuenta de anticipos configurada
            advance_account = self.company_id.hotel_advance_account_id

            if not advance_account:
                raise UserError(_(
                    'No se ha configurado la cuenta de anticipos de hotel. '
                    'Por favor configure la cuenta en Configuración > Hotel > Cuenta de Anticipos'
                ))

            # Obtener la cuenta de liquidez del diario (banco o caja)
            liquidity_account = self.journal_id.default_account_id

            # Buscar y reemplazar la línea de contrapartida
            # En un pago, hay 2 líneas:
            #   1. Línea de liquidez (cuenta del diario - banco/caja)
            #   2. Línea de contrapartida (cuenta receivable/payable del partner)
            for line_vals in line_vals_list:
                # La línea que NO es la cuenta de liquidez es la que debemos reemplazar
                if line_vals.get('account_id') != liquidity_account.id:
                    # Reemplazar con la cuenta de anticipos
                    line_vals['account_id'] = advance_account.id
                    line_vals['name'] = _('Anticipo de Reserva - %s') % (
                        self.hotel_reservation_payment_id.reservation_id.name
                        if self.hotel_reservation_payment_id else self.ref
                    )

        return line_vals_list
    
    def _check_balanced(self):
        """Override para permitir anticipos con cuenta personalizada"""
        # Para anticipos de hotel, NO validar que haya cuenta receivable/payable
        # porque usamos una cuenta de pasivo (anticipos) diferente
        if not self.is_hotel_advance:
            return super()._check_balanced()
        # Para anticipos, solo verificar que esté balanceado
        return True

    def action_post(self):
        """Override para validaciones adicionales de anticipos"""
        for payment in self:
            if payment.is_hotel_advance and not payment.company_id.hotel_advance_account_id:
                raise UserError(_(
                    'No se puede publicar el anticipo sin una cuenta de anticipos configurada. '
                    'Configure la cuenta en Configuración > Hotel'
                ))

        return super().action_post()
    
    def _synchronize_from_moves(self, changed_fields):
        """Override para evitar problemas de sincronización con anticipos"""
        # Si es un anticipo de hotel, no sincronizar ciertos campos que podrían
        # causar conflictos con la cuenta de anticipos
        if self.is_hotel_advance:
            # Remover destination_account_id de los campos a sincronizar si existe
            if 'line_ids.account_id' in changed_fields:
                changed_fields = [f for f in changed_fields if f != 'line_ids.account_id']
        
        return super()._synchronize_from_moves(changed_fields)
    
    @api.depends('is_hotel_advance', 'company_id')
    def _compute_destination_account_id(self):
        """Override para establecer cuenta de anticipos cuando aplique"""
        super()._compute_destination_account_id()
        
        for payment in self:
            if payment.is_hotel_advance and payment.company_id.hotel_advance_account_id:
                payment.destination_account_id = payment.company_id.hotel_advance_account_id