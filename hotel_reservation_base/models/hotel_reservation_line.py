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
        currency_field='price_currency_id'
    )
    
    price_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda del Precio',
        default=lambda self: self.env.company.currency_id,
        help='Moneda del precio unitario'
    )
    
    currency_rate = fields.Float(
        string='Tasa de Cambio',
        compute='_compute_currency_rate',
        store=True,
        digits=(12, 6),
        help='Tasa de cambio al momento del registro'
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
    
    @api.depends('price_currency_id', 'currency_id', 'date')
    def _compute_currency_rate(self):
        """Calcula y almacena la tasa de cambio al momento del registro"""
        for line in self:
            if line.price_currency_id and line.currency_id and line.price_currency_id != line.currency_id:
                # Obtener la tasa de cambio en la fecha del consumo
                line.currency_rate = line.price_currency_id._get_conversion_rate(
                    line.price_currency_id,
                    line.currency_id,
                    line.company_id or self.env.company,
                    line.date or fields.Date.today()
                )
            else:
                line.currency_rate = 1.0
    
    @api.depends('quantity', 'price_unit', 'tax_ids', 'price_currency_id', 'currency_id', 'currency_rate')
    def _compute_amount(self):
        """Calcula subtotal y total con impuestos en la moneda de la reserva"""
        for line in self:
            # Convertir precio a la moneda de la reserva si es necesario
            if line.price_currency_id and line.currency_id:
                if line.price_currency_id == line.currency_id:
                    price_unit_reservation_currency = line.price_unit
                else:
                    # Usar la tasa almacenada o calcular una nueva
                    price_unit_reservation_currency = line.price_currency_id._convert(
                        line.price_unit,
                        line.currency_id,
                        line.company_id or self.env.company,
                        line.date or fields.Date.today()
                    )
            else:
                price_unit_reservation_currency = line.price_unit
            
            price = price_unit_reservation_currency * line.quantity
            line.price_subtotal = price
            
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    price_unit=price_unit_reservation_currency,
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
                    currency=self.price_currency_id,
                    date=self.date or fields.Date.today()
                )
                self.price_unit = price
                # La moneda del precio será la de la lista de precios
                self.price_currency_id = self.pricelist_id.currency_id
            else:
                self.price_unit = self.product_id.lst_price
                self.price_currency_id = self.currency_id
            
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
                currency=self.price_currency_id,
                date=self.date or fields.Date.today()
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