# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev
{
    'name': 'Hotel Reservation Base',
    'version': '17.0.1.2.0',
    'category': 'Hotel',
    'summary': 'Sistema base de gestión de reservas hoteleras con soporte PMS y múltiples huéspedes',
    'description': """
        Módulo base que gestiona el ciclo de vida de las reservas hoteleras.
        Funciona como contenedor central de todos los consumos y pagos durante
        la estadía del huésped.

        Características principales:
        - Gestión completa del ciclo de reservas
        - Gestión de múltiples huéspedes por reserva
        - Registro de consumos manuales (en moneda de resguardo)
        - Integración con sistema PMS externo
        - Control de anticipos y pagos parciales
        - Cálculo automático de saldos
        - Sistema de bloqueo/desbloqueo de reservas
        - Integración con contabilidad
        - Sistema de moneda alternativa para economías inflacionarias
        - Conversión automática de pagos con tasas históricas
    """,
    'author': 'Almus Dev (JDV-ALM)',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'account',
        'sale_management',
        'point_of_sale',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/sequence_data.xml',

        # Wizards
        'wizards/hotel_payment_wizard_views.xml',
        
        # Views
        'views/hotel_reservation_views.xml',
        'views/hotel_reservation_line_views.xml',
        'views/hotel_reservation_pms_line_views.xml',
        'views/hotel_reservation_guest_views.xml',
        'views/hotel_reservation_payment_views.xml',
        'views/res_config_settings_views.xml',
        'views/menuitems.xml',
        
    ],
    'assets': {
        'web.assets_backend': [
            # Add any JS/CSS files here if needed
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}