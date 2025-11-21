# Guía de Troubleshooting - Sale Stock Validation

## El módulo no está bloqueando órdenes sin stock

Si después de actualizar el módulo a la versión 1.0.2 sigues pudiendo confirmar órdenes sin stock, sigue estos pasos:

### Paso 1: Verificar que el módulo está cargado

1. **Reiniciar Odoo** (importante para que cargue el código actualizado)
   ```bash
   sudo systemctl restart odoo
   # O el comando que uses para reiniciar tu instancia
   ```

2. **Verificar en los logs** al iniciar Odoo debe aparecer:
   ```
   ================================================================================
   MÓDULO SALE_STOCK_VALIDATION CARGADO - Validación de stock activa
   ================================================================================
   ```

3. Si NO aparece este mensaje, el módulo no está cargado. Verifica:
   - Que el módulo esté instalado (no solo descargado)
   - Que no haya errores de sintaxis en el código
   - Que el módulo esté en la lista de addons_path de Odoo

### Paso 2: Actualizar el módulo

Después de reiniciar, actualiza el módulo:

**Opción A - Desde interfaz:**
1. Apps → Quitar filtro "Apps"
2. Buscar "Sale Stock Validation"
3. Menú (⋮) → Actualizar

**Opción B - Desde línea de comandos:**
```bash
odoo-bin -u sale_stock_validation -d nombre_base_datos --stop-after-init
```

### Paso 3: Probar con logging visible

1. **Configurar logs en modo debug:**
   Edita tu archivo de configuración de Odoo (`odoo.conf`) y agrega:
   ```ini
   log_level = warning
   ```

2. **Reinicia Odoo**

3. **Intenta confirmar una orden** sin stock. Debes ver en los logs:
   ```
   ================================================================================
   SALE_STOCK_VALIDATION: Validando orden S03XXX
   ================================================================================
   Orden S03XXX: X líneas para validar de Y líneas totales
   Ejecutando validación de stock para orden S03XXX
   VALIDACIÓN STOCK - Producto: [Nombre] | Almacén: [Nombre] | Requerido: 20000.00 | Total: 17000.00 | Reservado: 0.00 | Disponible: 17000.00
   ❌ STOCK INSUFICIENTE - [Nombre]: Requerido 20000.00, Disponible 17000.00
   BLOQUEANDO CONFIRMACIÓN - 1 productos sin stock
   ```

4. **Si NO ves estos logs**, el módulo no se está ejecutando. Posibles causas:
   - Otro módulo está sobrescribiendo el método `action_confirm` después
   - El módulo no está correctamente actualizado
   - Hay un error en el código que impide su ejecución

### Paso 4: Verificar orden de carga de módulos

Si otros módulos personalizan `action_confirm` de `sale.order`, el orden importa:

1. **Verifica módulos que heredan sale.order:**
   ```bash
   grep -r "class.*SaleOrder" --include="*.py" /ruta/a/addons/
   grep -r "_inherit.*sale.order" --include="*.py" /ruta/a/addons/
   ```

2. **Identifica conflictos:** Busca otros módulos que sobrescriban `action_confirm`

3. **Solución:** Asegúrate que `sale_stock_validation` se cargue DESPUÉS de otros módulos que modifiquen `sale.order.action_confirm`

### Paso 5: Verificar configuración de productos

Algunos módulos permiten configurar productos para permitir stock negativo:

1. **En el producto:** 
   - Ir a Inventario → Productos
   - Abrir el producto
   - Pestaña "Inventario"
   - Verificar que "Permitir stock negativo" NO esté marcado

2. **En la categoría del producto:**
   - Ir a Configuración → Categorías de productos
   - Verificar que "Permitir stock negativo" NO esté marcado

### Paso 6: Verificar que el producto es almacenable

El módulo SOLO valida productos con `type='product'`:

1. Ir al producto
2. Pestaña "Información general"
3. Tipo de producto debe ser: **"Producto almacenable"**
4. Si es "Consumible" o "Servicio", NO se validará el stock

### Paso 7: Verificar la línea de orden

El módulo excluye ciertas líneas:

- Líneas de sección (display_type)
- Líneas de nota (display_type)
- Anticipos (is_downpayment)
- Productos sin ID

### Paso 8: Debug directo en Python

Si todo lo anterior falla, conecta por SSH y ejecuta:

```python
# Conectar a la base de datos
import odoorpc

odoo = odoorpc.ODOO('localhost', port=8069)
odoo.login('nombre_bd', 'usuario', 'password')

# Obtener una orden
SaleOrder = odoo.env['sale.order']
order = SaleOrder.browse(179)  # ID de tu orden

# Verificar que el método existe
print(hasattr(order, '_check_stock_availability'))

# Probar manualmente
lines = [l for l in order.order_line if l.product_id and l.product_id.type == 'product']
print(f"Líneas a validar: {len(lines)}")

# Ejecutar validación
try:
    order._check_stock_availability(lines)
    print("No se lanzó error - HAY STOCK SUFICIENTE")
except Exception as e:
    print(f"ERROR LANZADO: {e}")
```

## Contacto

Si después de seguir todos estos pasos el problema persiste:

1. Captura los logs completos desde que inicias Odoo hasta que intentas confirmar la orden
2. Verifica qué otros módulos personalizados tienes instalados
3. Comparte la información técnica completa

**Desarrollado por:** Almus Dev (JDV-ALM)  
**Website:** https://www.almus.dev