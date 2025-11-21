# -*- coding: utf-8 -*-
{
    'name': 'BCV Currency Rate Provider',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Obtiene tasas de cambio del Banco Central de Venezuela',
    'description': """
        Proveedor de tasas de cambio del Banco Central de Venezuela (BCV)
        ==================================================================
        
        Características:
        ---------------
        * Proveedor independiente de tasas BCV con cron propio
        * Compatible con VES, VEF y USD como moneda base
        * Web scraping del sitio oficial del BCV
        * Cron job independiente y configurable
        * Opción para actualizar solo en días hábiles
        * Opción para usar tasa del lunes en fin de semana
        * Sistema de logs detallado para debugging
        
        Configuración:
        -------------
        1. Instalar el módulo
        2. Ir a Configuración → Contabilidad → Monedas
        3. Seleccionar "Banco Central de Venezuela" como proveedor
        4. El cron se activa automáticamente
        5. Configurar actualización en días hábiles si se desea
        6. Configurar uso de tasa del lunes para fin de semana
        
        Debug:
        ------
        * Los logs usan el prefijo [BCV] para fácil filtrado
        * Acción manual disponible para pruebas
        * Verificar cron en: Configuración → Técnico → Acciones planificadas
        
        Nota sobre Fin de Semana:
        -------------------------
        El BCV publica los viernes en la noche la tasa que regirá el lunes.
        Si activa "Fin de Semana, tasa de lunes", el sistema usará esa tasa
        para operaciones del sábado y domingo.
    """,
    'author': 'Tu Empresa',
    'website': 'https://tu-sitio.com',
    'depends': [
        'base',
        'currency_rate_live',
    ],
    'external_dependencies': {
        'python': ['requests', 'beautifulsoup4'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
