# BCV Currency Rate Provider

## 📌 Descripción

Módulo de Odoo 18 para obtener tasas de cambio del Banco Central de Venezuela (BCV) mediante web scraping.

## ✨ Características

- ✅ **Cron propio independiente** - No depende de `currency_rate_live`
- ✅ **Soporte para VES, VEF y USD** como moneda base
- ✅ **Web scraping del BCV** - Obtiene USD y EUR
- ✅ **Actualización solo días hábiles** - Configurable
- ✅ **Tasa del lunes en fin de semana** - El BCV publica el viernes la tasa del lunes
- ✅ **Sistema de logs detallado** - Prefijo [BCV] para fácil debug
- ✅ **Botones de prueba** - Conexión y actualización manual

## 📦 Instalación

1. **Copiar el módulo** a la carpeta de addons de Odoo:
   ```bash
   cp -r bcv_currency_provider /path/to/odoo/addons/
   ```

2. **Instalar dependencias Python**:
   ```bash
   pip install requests beautifulsoup4
   ```

3. **Actualizar lista de aplicaciones** en Odoo:
   - Configuración → Aplicaciones → Actualizar lista de aplicaciones

4. **Instalar el módulo**:
   - Buscar "BCV Currency Rate Provider"
   - Instalar

## ⚙️ Configuración

1. Ir a **Configuración → Contabilidad → Monedas**
2. En "Proveedor de Tasas de Cambio" seleccionar **"Banco Central de Venezuela"**
3. Configurar las opciones:
   - **Actualizar solo días hábiles**: Solo actualiza de lunes a viernes
   - **Fin de Semana, tasa de lunes**: Usa la tasa del lunes para sábado y domingo

## 🔍 Debug y Logs

### Ver logs en tiempo real:
```bash
tail -f /var/log/odoo/odoo.log | grep "\[BCV\]"
```

### Ver solo errores:
```bash
grep "\[BCV\].*ERROR" /var/log/odoo/odoo.log
```

### Ver resumen de actualizaciones:
```bash
grep "\[BCV\] RESUMEN" /var/log/odoo/odoo.log
```

## 📋 Uso Manual

### Desde la interfaz:
1. Ir a **Configuración → Contabilidad**
2. En la sección BCV:
   - **Probar Conexión**: Verifica el acceso al sitio del BCV
   - **Actualizar Ahora**: Fuerza una actualización manual

### Desde el Shell de Odoo:
```python
# Verificar configuración
companies = env['res.company'].search([('currency_provider', '=', 'bcv')])
for c in companies:
    print(f"{c.name}: Días hábiles={c.can_update_habil_days}, Tasa lunes={c.bcv_weekend_use_monday}")

# Actualizar manualmente
companies.bcv_update_currency_rates()

# Ver último error
for c in companies:
    print(f"{c.name}: {c.bcv_last_error or 'Sin errores'}")
```

## 📅 Comportamiento de Fin de Semana

### Sin opción "Fin de Semana, tasa de lunes":
- **Viernes**: Actualiza con tasa del viernes
- **Sábado y Domingo**: No actualiza (si está activo "solo días hábiles")

### Con opción "Fin de Semana, tasa de lunes":
- **Viernes**: Actualiza con tasa del viernes
- **Sábado y Domingo**: Usa la tasa publicada el viernes (que es la del lunes)
- **Lunes**: Usa la misma tasa

### Ejemplo práctico:
```
Viernes 10/01: El BCV publica USD = 40.50 (tasa del viernes)
Viernes noche: El BCV publica USD = 40.60 (tasa del lunes)

Con la opción activada:
- Operaciones del sábado 11/01: USD = 40.60
- Operaciones del domingo 12/01: USD = 40.60  
- Operaciones del lunes 13/01: USD = 40.60
```

## 🐛 Solución de Problemas

### El cron no se ejecuta:
1. Verificar en **Configuración → Técnico → Acciones planificadas**
2. Buscar "BCV: Actualización de Tasas de Cambio"
3. Verificar que esté activo
4. Revisar la fecha de próxima ejecución

### No se obtienen tasas:
1. Usar el botón "Probar Conexión"
2. Verificar los logs con `grep "\[BCV\]" /var/log/odoo/odoo.log`
3. Verificar que el sitio https://www.bcv.org.ve esté accesible

### Tasas incorrectas para VES:
- El módulo calcula automáticamente la tasa inversa
- Si el BCV dice 1 USD = 40.50 VES
- El módulo guarda 1 VES = 0.0247 USD (1/40.50)

## 📝 Notas Técnicas

- **Método principal**: `bcv_update_currency_rates()` (no usa el de currency_rate_live)
- **Cron ID**: `bcv_currency_provider.ir_cron_bcv_currency_update`
- **Scraper**: Busca elementos con id="dolar" y id="euro" en el HTML del BCV
- **Timeout**: 20 segundos para la conexión al BCV

## 📄 Licencia

LGPL-3

## 👨‍💻 Autor

Tu Empresa - https://tu-sitio.com

## 🆘 Soporte

Para soporte, revisar los logs con prefijo [BCV] o contactar al administrador del sistema.
