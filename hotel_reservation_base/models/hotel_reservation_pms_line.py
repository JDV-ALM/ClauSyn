# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HotelReservationPMSLine(models.Model):
    _name = 'hotel.reservation.pms.line'
    _description = 'Línea de Consumo PMS'
    _order = 'date desc, id desc'

    reservation_id = fields.Many2one(
        'hotel.reservation',
        string='Reserva',
        required=True,
        ondelete='cascade',
        index=True
    )

    name = fields.Char(
        string='Descripción',
        required=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        domain=[('sale_ok', '=', True)],
        help='Producto relacionado (opcional)'
    )

    quantity = fields.Float(
        string='Cantidad',
        required=True,
        default=1.0,
        digits='Product Unit of Measure'
    )

    price_unit = fields.Monetary(
        string='Precio Unitario',
        required=True,
        currency_field='currency_id',
        help='Precio unitario en moneda de resguardo'
    )

    tax_ids = fields.Many2many(
        'account.tax',
        string='Impuestos',
        domain=[('type_tax_use', '=', 'sale')],
        help='Impuestos aplicables'
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    price_total = fields.Monetary(
        string='Total',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    date = fields.Datetime(
        string='Fecha',
        required=True,
        default=fields.Datetime.now
    )

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True
    )

    # Campos relacionados con PMS
    pms_reference = fields.Char(
        string='Referencia PMS',
        help='Referencia del registro en el sistema PMS externo',
        index=True
    )

    pms_sync_date = fields.Datetime(
        string='Fecha Sincronización',
        help='Fecha y hora de sincronización desde el PMS',
        default=fields.Datetime.now
    )

    # Campos relacionados
    currency_id = fields.Many2one(
        related='reservation_id.currency_id',
        string='Moneda de Resguardo',
        readonly=True,
        store=True,
        help='Todas las líneas PMS están en la moneda de resguardo de la reserva'
    )

    company_id = fields.Many2one(
        related='reservation_id.company_id',
        string='Compañía',
        readonly=True,
        store=True
    )

    partner_id = fields.Many2one(
        related='reservation_id.partner_id',
        string='Cliente',
        readonly=True,
        store=True
    )

    state = fields.Selection(
        related='reservation_id.state',
        string='Estado Reserva',
        readonly=True,
        store=True
    )

    @api.depends('quantity', 'price_unit', 'tax_ids')
    def _compute_amount(self):
        """Calcula subtotal y total con impuestos en la moneda de resguardo"""
        for line in self:
            price = line.price_unit * line.quantity
            line.price_subtotal = price

            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    price_unit=line.price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id
                )
                line.price_total = taxes['total_included']
            else:
                line.price_total = line.price_subtotal

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('La cantidad debe ser mayor a cero'))

    @api.constrains('price_unit')
    def _check_price_unit(self):
        for line in self:
            if line.price_unit < 0:
                raise ValidationError(_('El precio unitario no puede ser negativo'))

    def name_get(self):
        result = []
        for line in self:
            name = line.name
            if line.pms_reference:
                name = f"[{line.pms_reference}] {name}"
            result.append((line.id, name))
        return result
