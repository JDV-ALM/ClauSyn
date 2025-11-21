# -*- coding: utf-8 -*-

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Moneda USD para los campos monetarios
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        default=lambda self: self.env.ref('base.USD'),
        readonly=True,
    )
    
    # Costo Ref - Se actualiza automáticamente cuando cambia standard_price
    cost_usd_ref = fields.Monetary(
        string='Costo Ref (USD)',
        currency_field='currency_usd_id',
        store=True,
        readonly=True,
        help='Costo referencial en USD. Se actualiza automáticamente cuando cambia el costo estándar.'
    )
    
    # Costo Fijo - Solo modificable por importación
    cost_usd_fixed = fields.Monetary(
        string='Costo Fijo (USD)',
        currency_field='currency_usd_id',
        store=True,
        readonly=True,
        help='Costo fijo en USD. Solo modificable mediante importación masiva.'
    )
    
    # Fecha de última actualización del Costo Ref
    cost_usd_ref_date = fields.Datetime(
        string='Fecha Act. Costo Ref',
        readonly=True,
        help='Fecha de última actualización del Costo Ref USD'
    )

    def write(self, vals):
        """Override write para actualizar cost_usd_ref cuando cambia standard_price"""
        
        # Si standard_price está en vals, calcular el nuevo cost_usd_ref
        if 'standard_price' in vals:
            new_standard_price = vals['standard_price']
            
            for product in self:
                # Solo actualizar si el precio realmente cambió
                if new_standard_price != product.standard_price and new_standard_price > 0:
                    # Convertir de VES a USD
                    company_currency = self.env.company.currency_id
                    usd_currency = self.env.ref('base.USD')
                    
                    # Conversión a USD con la tasa actual
                    cost_usd = company_currency._convert(
                        new_standard_price,
                        usd_currency,
                        self.env.company,
                        fields.Date.today()
                    )
                    
                    # Agregar a vals para actualizar junto con standard_price
                    vals['cost_usd_ref'] = cost_usd
                    vals['cost_usd_ref_date'] = fields.Datetime.now()
                    
                    _logger.info(
                        "Actualizando Costo Ref USD para %s: %s VES -> %s USD (Tasa: %s)",
                        product.display_name,
                        new_standard_price,
                        round(cost_usd, 2),
                        round(new_standard_price / cost_usd, 2) if cost_usd else 0
                    )
        
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para establecer cost_usd_ref inicial si tiene standard_price"""
        
        company_currency = self.env.company.currency_id
        usd_currency = self.env.ref('base.USD')
        
        for vals in vals_list:
            # Si se está creando con standard_price, calcular cost_usd_ref
            if vals.get('standard_price', 0) > 0:
                cost_usd = company_currency._convert(
                    vals['standard_price'],
                    usd_currency,
                    self.env.company,
                    fields.Date.today()
                )
                vals['cost_usd_ref'] = cost_usd
                vals['cost_usd_ref_date'] = fields.Datetime.now()
        
        return super().create(vals_list)


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    # Campos relacionados para mostrar en template cuando hay una sola variante
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        related='product_variant_ids.currency_usd_id',
        readonly=True,
    )
    
    cost_usd_ref = fields.Monetary(
        string='Costo Ref (USD)',
        related='product_variant_ids.cost_usd_ref',
        readonly=True,
        currency_field='currency_usd_id',
    )
    
    cost_usd_fixed = fields.Monetary(
        string='Costo Fijo (USD)',
        related='product_variant_ids.cost_usd_fixed',
        readonly=True,
        currency_field='currency_usd_id',
    )
    
    cost_usd_ref_date = fields.Datetime(
        string='Fecha Act. Costo Ref',
        related='product_variant_ids.cost_usd_ref_date',
        readonly=True,
    )
