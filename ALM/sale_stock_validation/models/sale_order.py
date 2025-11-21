# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """
        Valida stock usando la misma lógica que el widget de inventario.
        """
        for order in self:
            # Forzar el cálculo del widget
            order.order_line._compute_qty_at_date()
            order.order_line._compute_qty_to_deliver()
            
            # Buscar líneas que tendrían el widget en rojo
            problematic_lines = []
            
            for line in order.order_line:
                # El widget se muestra cuando:
                # - display_qty_widget es True
                # - Y free_qty_today < qty_to_deliver (para no-MTO)
                
                if not line.display_qty_widget:
                    continue
                    
                # Para productos no-MTO, el widget está rojo cuando no hay stock
                if not line.is_mto and line.free_qty_today < line.qty_to_deliver:
                    problematic_lines.append(line)
            
            if problematic_lines:
                order._raise_stock_error(problematic_lines)
        
        return super().action_confirm()

    def _raise_stock_error(self, lines):
        """
        Genera mensaje de error para las líneas problemáticas.
        """
        message = _("⚠️ No se puede confirmar la orden\n\n")
        message += _("Los siguientes productos no tienen stock suficiente:\n\n")
        
        for line in lines:
            message += _("• %s\n", line.product_id.display_name)
            message += _("  Pendiente entregar: %.2f %s\n", 
                        line.qty_to_deliver, line.product_uom.name)
            message += _("  Disponible ahora: %.2f %s\n\n", 
                        max(0, line.free_qty_today), line.product_uom.name)
        
        message += _("Estos son los mismos productos que muestran el indicador rojo en la orden.")
        
        raise UserError(message)