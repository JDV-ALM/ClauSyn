# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    can_update_habil_days = fields.Boolean(
        related="company_id.can_update_habil_days",
        readonly=False,
        string="Actualizar BCV solo días hábiles"
    )
    
    bcv_weekend_use_monday = fields.Boolean(
        related="company_id.bcv_weekend_use_monday",
        readonly=False,
        string="Fin de Semana, tasa de lunes",
        help="El BCV publica los viernes en la noche la tasa del lunes. "
             "Si activa esta opción, las operaciones del sábado y domingo "
             "usarán la tasa del lunes."
    )
    
    bcv_last_update = fields.Datetime(
        related="company_id.bcv_last_update",
        readonly=True,
        string="Última actualización BCV"
    )
    
    bcv_last_error = fields.Text(
        related="company_id.bcv_last_error",
        readonly=True,
        string="Último error BCV"
    )

    def action_bcv_update_now(self):
        """
        Botón para actualizar manualmente desde configuración.
        """
        _logger.info("[BCV] Actualización manual desde configuración")
        return self.env['res.company'].action_bcv_update_now()
    
    def action_bcv_test_connection(self):
        """
        Botón para probar la conexión con el BCV.
        """
        _logger.info("[BCV] Probando conexión con el BCV...")
        
        from ..tools import bcv_scraper
        
        try:
            test_data = bcv_scraper.get_bcv_rates(self.company_id)
            if test_data:
                message = _(
                    "✓ Conexión exitosa\n"
                    "USD: %(usd)s\n"
                    "EUR: %(eur)s\n"
                    "Fecha: %(date)s"
                ) % {
                    'usd': test_data.get('USD', 'N/A'),
                    'eur': test_data.get('EUR', 'N/A'),
                    'date': test_data.get('date', 'N/A')
                }
                msg_type = 'success'
            else:
                message = _("✗ No se pudieron obtener datos del BCV")
                msg_type = 'warning'
        except Exception as e:
            message = _("✗ Error: %(error)s") % {'error': str(e)}
            msg_type = 'danger'
            _logger.error(f"[BCV] Error en prueba de conexión: {e}", exc_info=True)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Prueba de Conexión BCV'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }
    
    @api.onchange('bcv_weekend_use_monday')
    def _onchange_bcv_weekend_use_monday(self):
        """
        Mostrar información cuando se activa la opción de tasa del lunes.
        """
        if self.bcv_weekend_use_monday and not self.can_update_habil_days:
            return {
                'warning': {
                    'title': _('Configuración de Fin de Semana'),
                    'message': _(
                        'Ha activado "Fin de Semana, tasa de lunes".\n'
                        'El sistema usará la tasa del lunes para operaciones del sábado y domingo.\n'
                        'Nota: El BCV publica esta tasa los viernes en la noche.'
                    )
                }
            }
