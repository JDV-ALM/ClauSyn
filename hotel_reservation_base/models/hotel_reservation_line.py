# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HotelReservationLine(models.Model):
    _name = 'hotel.reservation.line'
    _description = 'Línea de Consumo de Reserva'
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
    
    is_manual = fields.Boolean(
        string='Cargo Manual',
        default=True,
        help='Indica si es un cargo manual'
    )
    
    # Campos relacionados
    currency_id = fields.Many2one(
        related='reservation_id.currency_id',
        string='Moneda',
        readonly=True,
        store=True
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
    
    pricelist_id = fields.Many2one(
        related='reservation_id.pricelist_id',
        string='Lista de Precios',
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
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Actualiza campos basados en el producto seleccionado"""
        if self.product_id:
            self.name = self.product_id.display_name

            # Obtener precio de la lista de precios si existe
            if self.pricelist_id:
                price = self.pricelist_id._get_product_price(
                    self.product_id,
                    self.quantity or 1.0,
                    currency=self.currency_id,
                    date=self.date or fields.Date.today()
                )
                # Si el precio está en otra moneda, convertir a moneda de resguardo
                if self.pricelist_id.currency_id != self.currency_id:
                    price = self.pricelist_id.currency_id._convert(
                        price,
                        self.currency_id,
                        self.company_id or self.env.company,
                        self.date or fields.Date.today()
                    )
                self.price_unit = price
            else:
                # Obtener precio del producto y convertir si es necesario
                product_price = self.product_id.lst_price
                product_currency = self.product_id.currency_id
                if product_currency != self.currency_id:
                    product_price = product_currency._convert(
                        product_price,
                        self.currency_id,
                        self.company_id or self.env.company,
                        self.date or fields.Date.today()
                    )
                self.price_unit = product_price

            # Obtener impuestos del producto
            taxes = self.product_id.taxes_id.filtered(
                lambda t: t.company_id == self.company_id
            )
            self.tax_ids = taxes

    @api.onchange('quantity')
    def _onchange_quantity(self):
        """Actualiza el precio cuando cambia la cantidad (puede haber descuentos por volumen)"""
        if self.product_id and self.pricelist_id:
            price = self.pricelist_id._get_product_price(
                self.product_id,
                self.quantity or 1.0,
                currency=self.currency_id,
                date=self.date or fields.Date.today()
            )
            # Si el precio está en otra moneda, convertir a moneda de resguardo
            if self.pricelist_id.currency_id != self.currency_id:
                price = self.pricelist_id.currency_id._convert(
                    price,
                    self.currency_id,
                    self.company_id or self.env.company,
                    self.date or fields.Date.today()
                )
            self.price_unit = price
    
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
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para validar estado de reserva"""
        lines = super().create(vals_list)
        for line in lines:
            if line.reservation_id.state not in ['draft', 'confirmed', 'checked_in']:
                raise ValidationError(
                    _('No se pueden agregar cargos a una reserva en estado %s') % line.reservation_id.state
                )
        return lines
    
    def unlink(self):
        """Override unlink para validar estado de reserva"""
        for line in self:
            if line.reservation_id.state not in ['draft', 'confirmed', 'checked_in']:
                raise ValidationError(
                    _('No se pueden eliminar cargos de una reserva en estado %s') % line.reservation_id.state
                )
        return super().unlink()