# Sale Stock Validation

## Descripción

Módulo para Odoo 18 que previene la confirmación de órdenes de venta cuando no hay stock suficiente disponible en el almacén configurado.

**Desarrollado por:** Almus Dev (JDV-ALM)  
**Website:** https://www.almus.dev

## Características

- ✅ Valida stock disponible antes de confirmar la orden de venta
- ✅ Verifica stock en el almacén específico de la orden (no en toda la base de datos)
- ✅ Maneja correctamente diferentes unidades de medida
- ✅ Mensaje de error claro y detallado
- ✅ Solo valida productos almacenables (type='product')
- ✅ Excluye líneas de sección, notas y anticipos

## Instalación

1. Copia la carpeta `sale_stock_validation` a tu directorio de addons de Odoo
2. Actualiza la lista de aplicaciones
3. Instala el módulo "Sale Stock Validation"

## Uso

Una vez instalado, el módulo funciona automáticamente:

- Al intentar confirmar una cotización, valida el stock disponible
- Si hay productos sin stock suficiente, muestra un error con:
  - Nombre del producto
  - Cantidad requerida
  - Cantidad disponible
  - Almacén donde se validó

## Dependencias

- `sale_stock`

## Versión

- **Odoo:** 18.0
- **Módulo:** 1.0.2

## Troubleshooting

Si el módulo no está bloqueando órdenes sin stock:

### 1. Verificar que el módulo está instalado y actualizado
```bash
# En el log de Odoo al reiniciar debe aparecer:
MÓDULO SALE_STOCK_VALIDATION CARGADO - Validación de stock activa
```

### 2. Actualizar el módulo
```bash
# Desde línea de comandos:
odoo-bin -u sale_stock_validation -d nombre_bd

# O desde Odoo:
# Apps > Buscar "Sale Stock Validation" > Actualizar
```

### 3. Verificar logs al confirmar una orden
Al confirmar una orden de venta, deben aparecer logs como:
```
SALE_STOCK_VALIDATION: Validando orden S03XXX
VALIDACIÓN STOCK - Producto: [Nombre] | Requerido: X | Disponible: Y
```

### 4. Verificar que no hay otros módulos interfiriendo
- Módulos como `stock_no_negative` pueden permitir stock negativo si están configurados
- Revisar en el producto: "Permitir stock negativo" debe estar desmarcado
- Revisar en la categoría del producto: "Permitir stock negativo" debe estar desmarcado

### 5. Verificar la configuración del almacén
- El almacén de la orden debe tener una ubicación de stock válida
- La ubicación debe ser del tipo "Vista" o "Interna"

## Changelog

### v1.0.2 (2025-11-11)
- 🔧 **MEJORA CRÍTICA**: Refactorización completa del método de validación
  - Cambio de `stock.quant._get_available_quantity()` a consulta directa de quants
  - Agregado logging extensivo con nivel WARNING para mejor visibilidad
  - Cálculo directo: `cantidad_disponible = cantidad_total - cantidad_reservada`
  - Mensaje de error mejorado con emojis y mejor formato
  - Log al cargar el módulo para confirmar que está activo
  - Logging detallado de cada validación de producto
  
### v1.0.1 (2025-11-11)
- 🐛 **FIX**: Corregido bug que permitía confirmar órdenes sin stock suficiente
  - Problema: El módulo usaba `product.free_qty` que no calculaba correctamente
  - Solución: Implementado `stock.quant._get_available_quantity()`

### v1.0.0 (Inicial)
- Primera versión del módulo

## Licencia

LGPL-3

## Soporte

Para soporte o consultas, visita: https://www.almus.dev
