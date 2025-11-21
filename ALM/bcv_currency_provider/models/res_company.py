# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ..tools import bcv_scraper
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Banco Central de Venezuela")],
        ondelete={'bcv': 'cascade'}
    )
    
    can_update_habil_days = fields.Boolean(
        string="Actualizar solo días hábiles",
        default=True,
        help="Si está activo, solo actualizará las tasas de lunes a viernes"
    )
    
    bcv_weekend_use_monday = fields.Boolean(
        string="Fin de Semana, tasa de lunes",
        default=False,
        help="Si está activo, las operaciones del sábado y domingo usarán la tasa del lunes. "
             "El BCV publica los viernes en la noche la tasa que regirá el lunes."
    )
    
    bcv_last_update = fields.Datetime(
        string="Última actualización BCV",
        readonly=True,
        help="Fecha y hora de la última actualización exitosa del BCV"
    )
    
    bcv_last_error = fields.Text(
        string="Último error BCV",
        readonly=True,
        help="Último error ocurrido durante la actualización"
    )

    @api.model
    def bcv_update_currency_rates(self):
        """
        Método principal para actualizar tasas BCV.
        Este es NUESTRO método, no dependemos del cron de currency_rate_live.
        Llamado directamente por nuestro cron: ir_cron_bcv_currency_update
        """
        _logger.info("[BCV] ==========================================")
        _logger.info("[BCV] Iniciando actualización de tasas BCV")
        _logger.info(f"[BCV] Fecha/Hora: {fields.Datetime.now()}")
        _logger.info(f"[BCV] Usuario: {self.env.user.name}")
        _logger.info("[BCV] ==========================================")
        
        # Asegurar que solo procesamos empresas con BCV
        if self:
            companies = self.filtered(lambda c: c.currency_provider == 'bcv')
        else:
            companies = self.search([('currency_provider', '=', 'bcv')])
        
        if not companies:
            _logger.warning("[BCV] No hay empresas con proveedor BCV configurado")
            return False
        
        _logger.info(f"[BCV] Empresas a procesar: {', '.join(companies.mapped('name'))}")
        
        success_count = 0
        error_count = 0
        
        for company in companies:
            _logger.info(f"[BCV] {'='*50}")
            _logger.info(f"[BCV] Procesando: {company.name}")
            _logger.info(f"[BCV] Moneda base: {company.currency_id.name}")
            _logger.info(f"[BCV] Config fin de semana: {company.bcv_weekend_use_monday}")
            _logger.info(f"[BCV] {'='*50}")
            
            try:
                result = company._bcv_perform_update()
                if result:
                    success_count += 1
                    company.bcv_last_update = fields.Datetime.now()
                    company.bcv_last_error = False
                    _logger.info(f"[BCV] ✓ {company.name}: Actualización exitosa")
                else:
                    error_count += 1
                    _logger.warning(f"[BCV] ⚠ {company.name}: No se obtuvieron tasas")
                    
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                company.bcv_last_error = f"{fields.Datetime.now()}: {error_msg}"
                _logger.error(f"[BCV] ✗ {company.name}: ERROR - {error_msg}", exc_info=True)
        
        _logger.info("[BCV] ==========================================")
        _logger.info(f"[BCV] RESUMEN DE ACTUALIZACIÓN:")
        _logger.info(f"[BCV] - Exitosas: {success_count}")
        _logger.info(f"[BCV] - Con errores: {error_count}")
        _logger.info(f"[BCV] - Total procesadas: {len(companies)}")
        _logger.info("[BCV] ==========================================")
        
        return success_count > 0

    def _bcv_should_update(self):
        """
        Determina si la empresa debe actualizar sus tasas hoy.
        Considera la configuración de días hábiles pero NO la de fin de semana.
        La actualización siempre ocurre, solo cambia qué fecha se usa para guardar.
        """
        self.ensure_one()
        
        current_date = fields.Date.context_today(self)
        weekday = current_date.weekday()  # 0=Lunes, 6=Domingo
        is_weekend = weekday >= 5
        
        _logger.info(f"[BCV] Verificando día para {self.name}:")
        _logger.info(f"[BCV]   - Fecha: {current_date}")
        _logger.info(f"[BCV]   - Día semana: {weekday} ({'Fin de semana' if is_weekend else 'Día hábil'})")
        _logger.info(f"[BCV]   - Config días hábiles: {self.can_update_habil_days}")
        _logger.info(f"[BCV]   - Config tasa lunes: {self.bcv_weekend_use_monday}")
        
        # Si está configurado para no actualizar en fin de semana Y no está la opción de tasa del lunes
        if self.can_update_habil_days and is_weekend and not self.bcv_weekend_use_monday:
            _logger.info(f"[BCV]   → Resultado: NO actualizar (fin de semana sin tasa lunes)")
            return False
        
        _logger.info(f"[BCV]   → Resultado: SÍ actualizar")
        return True

    def _bcv_get_rate_date(self, bcv_date):
        """
        Determina qué fecha usar para guardar la tasa según la configuración.
        
        Args:
            bcv_date: Fecha obtenida del BCV
            
        Returns:
            date: Fecha a usar para guardar la tasa
        """
        self.ensure_one()
        
        current_date = fields.Date.context_today(self)
        weekday = current_date.weekday()  # 0=Lunes, 6=Domingo
        
        # Si estamos en fin de semana y está activa la opción de tasa del lunes
        if weekday >= 5 and self.bcv_weekend_use_monday:
            # Calcular el próximo lunes
            days_until_monday = (7 - weekday) % 7
            if days_until_monday == 0:  # Si es lunes
                monday_date = current_date
            else:
                monday_date = current_date + timedelta(days=days_until_monday)
            
            _logger.info(f"[BCV] Fin de semana con tasa de lunes activa:")
            _logger.info(f"[BCV]   - Fecha actual: {current_date} ({self._get_weekday_name(weekday)})")
            _logger.info(f"[BCV]   - Usando fecha del lunes: {monday_date}")
            
            # Crear tasas para sábado, domingo y lunes
            return {
                'dates': [current_date, monday_date],  # Lista de fechas para crear
                 'primary_date': monday_date,  # Fecha principal para logs
            }
        
        # Caso normal: usar la fecha del BCV o la fecha actual
        return {
            'dates': [bcv_date or current_date],
            'primary_date': bcv_date or current_date,
        }
    
    def _get_weekday_name(self, weekday):
        """Retorna el nombre del día de la semana en español."""
        days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return days[weekday] if 0 <= weekday <= 6 else 'Desconocido'

    def _bcv_perform_update(self):
        """
        Realiza la actualización de tasas para una empresa.
        Ahora maneja la lógica de fin de semana con tasa del lunes.
        """
        self.ensure_one()
        
        # Verificar si debemos actualizar
        if not self._bcv_should_update():
            return False
        
        _logger.info(f"[BCV] Obteniendo monedas activas...")
        
        # Obtener monedas disponibles
        Currency = self.env['res.currency']
        currencies = Currency.search([
            ('active', '=', True),
            ('id', '!=', self.currency_id.id)
        ])
        
        _logger.info(f"[BCV] Monedas encontradas: {', '.join(currencies.mapped('name'))}")
        
        # Obtener tasas del BCV
        _logger.info(f"[BCV] Conectando con el sitio del BCV...")
        rates = self._parse_bcv_data(currencies)
        
        if not rates:
            _logger.warning(f"[BCV] No se obtuvieron tasas del BCV")
            return False
        
        _logger.info(f"[BCV] Tasas obtenidas: {len(rates)}")
        
        # Guardar las tasas
        CurrencyRate = self.env['res.currency.rate']
        created_count = 0
        updated_count = 0
        
        for currency_code, (rate, bcv_date) in rates.items():
            if currency_code == self.currency_id.name:
                continue
            
            currency = Currency.search([('name', '=', currency_code)], limit=1)
            if not currency:
                _logger.warning(f"[BCV] Moneda {currency_code} no encontrada en el sistema")
                continue
            
            # Determinar qué fechas usar según configuración
            date_info = self._bcv_get_rate_date(bcv_date)
            
            for rate_date in date_info['dates']:
                # Buscar tasa existente
                existing = CurrencyRate.search([
                    ('currency_id', '=', currency.id),
                    ('name', '=', rate_date),
                    ('company_id', '=', self.id)
                ], limit=1)
                
                if existing:
                    old_rate = existing.rate
                    if abs(old_rate - rate) > 0.0001:
                        existing.rate = rate
                        updated_count += 1
                        _logger.info(f"[BCV] ↻ {currency_code} para {rate_date}: {old_rate:.6f} → {rate:.6f}")
                    else:
                        _logger.info(f"[BCV] = {currency_code} para {rate_date}: {rate:.6f} (sin cambios)")
                else:
                    CurrencyRate.create({
                        'currency_id': currency.id,
                        'rate': rate,
                        'name': rate_date,
                        'company_id': self.id,
                    })
                    created_count += 1
                    _logger.info(f"[BCV] + {currency_code} para {rate_date}: {rate:.6f} (nueva)")
            
            # Log especial para fin de semana
            if len(date_info['dates']) > 1:
                _logger.info(f"[BCV] 📅 Tasa del lunes aplicada también al fin de semana para {currency_code}")
        
        _logger.info(f"[BCV] Resumen: {created_count} creadas, {updated_count} actualizadas")
        return True

    def _parse_bcv_data(self, available_currencies):
        """
        Obtiene y procesa las tasas del BCV.
        """
        self.ensure_one()
        
        available_currency_names = available_currencies.mapped('name')
        company_currency = self.currency_id.name
        
        _logger.info(f"[BCV] Parseando datos del BCV")
        _logger.info(f"[BCV]   Moneda empresa: {company_currency}")
        _logger.info(f"[BCV]   Monedas objetivo: {available_currency_names}")
        
        # Obtener datos del scraper
        bcv_data = bcv_scraper.get_bcv_rates(self)
        
        if not bcv_data:
            _logger.error("[BCV] El scraper no devolvió datos")
            return {}
        
        rates = {}
        usd_rate = bcv_data.get('USD')
        eur_rate = bcv_data.get('EUR')
        rate_date = bcv_data.get('date', fields.Date.context_today(self))
        
        _logger.info(f"[BCV] Datos del scraper:")
        _logger.info(f"[BCV]   - USD: {usd_rate}")
        _logger.info(f"[BCV]   - EUR: {eur_rate}")
        _logger.info(f"[BCV]   - Fecha: {rate_date}")
        
        # Cálculo según moneda base
        if company_currency in ['VES', 'VEF']:
            _logger.info(f"[BCV] Calculando tasas inversas (base {company_currency})")
            
            if 'USD' in available_currency_names and usd_rate:
                rates['USD'] = (1.0 / usd_rate, rate_date)
                _logger.info(f"[BCV]   USD: 1/{usd_rate} = {rates['USD'][0]:.6f}")
            
            if 'EUR' in available_currency_names and eur_rate:
                rates['EUR'] = (1.0 / eur_rate, rate_date)
                _logger.info(f"[BCV]   EUR: 1/{eur_rate} = {rates['EUR'][0]:.6f}")
                
        elif company_currency == 'USD':
            _logger.info(f"[BCV] Usando tasas directas (base USD)")
            
            if 'VES' in available_currency_names and usd_rate:
                rates['VES'] = (usd_rate, rate_date)
                _logger.info(f"[BCV]   VES: {usd_rate}")
            
            if 'VEF' in available_currency_names and usd_rate:
                rates['VEF'] = (usd_rate, rate_date)
                _logger.info(f"[BCV]   VEF: {usd_rate}")
            
            if 'EUR' in available_currency_names and eur_rate and usd_rate:
                cross_rate = eur_rate / usd_rate
                rates['EUR'] = (cross_rate, rate_date)
                _logger.info(f"[BCV]   EUR (cruzada): {eur_rate}/{usd_rate} = {cross_rate:.6f}")
                
        else:
            _logger.warning(f"[BCV] Moneda base {company_currency} no implementada")
        
        _logger.info(f"[BCV] Total tasas calculadas: {len(rates)}")
        return rates

    @api.model
    def action_bcv_update_now(self):
        """
        Acción manual para actualizar tasas BCV inmediatamente.
        Útil para debugging y pruebas.
        """
        _logger.info("[BCV] Actualización manual solicitada")
        
        companies = self.search([('currency_provider', '=', 'bcv')])
        if not companies:
            raise UserError(_("No hay empresas configuradas con proveedor BCV"))
        
        # Ejecutar actualización
        companies.bcv_update_currency_rates()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización BCV'),
                'message': _('Las tasas del BCV han sido actualizadas.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_bcv_view_logs(self):
        """
        Acción para ver los logs del BCV.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Logs BCV'),
                'message': _('Revisar logs del servidor con grep "[BCV]"'),
                'type': 'info',
                'sticky': True,
            }
        }

    # Método heredado por compatibilidad (NO usado por nuestro cron)
    def update_currency_rates(self):
        """
        Método del módulo currency_rate_live.
        Lo mantenemos por compatibilidad pero NO es usado por nuestro cron.
        """
        _logger.info("[BCV] ⚠ Llamada a update_currency_rates (método heredado)")
        
        # Ejecutar el método padre para otros proveedores
        res = super().update_currency_rates()
        
        # Si alguien llama este método, redirigir a nuestro método
        bcv_companies = self.filtered(lambda c: c.currency_provider == 'bcv')
        if bcv_companies:
            _logger.info("[BCV] Redirigiendo a bcv_update_currency_rates")
            bcv_companies.bcv_update_currency_rates()
        
        return res
