# Guía Técnica 2 — Creación y Gestión de Menús

**Software:** GastroSoft POS  
**Versión:** 2.1.5 (enero 2025)  
**Documento técnico** — Registro, edición y gestión de menús y productos.

## 1. Introducción

El módulo de Menú y Categorías permite gestionar de manera centralizada todos los productos ofrecidos por el restaurante: comidas, bebidas, extras y promociones.

Una correcta organización facilita la toma de pedidos, el cálculo automático de impuestos y la gestión de disponibilidad por turnos.

Este documento explica cómo crear categorías, registrar productos, definir precios y configurar opciones avanzadas.

## 2. Acceso al módulo de Menú

1. Inicie sesión con un perfil de **Administrador** o **Gerente**.

2. En el menú lateral izquierdo, seleccione:  
   **Configuración → Menú y Categorías**

3. El panel principal muestra:
   - Categorías existentes
   - Lista de productos por categoría
   - Opciones para agregar, editar o eliminar productos

## 3. Crear una categoría

Las categorías agrupan productos similares, facilitando su búsqueda y organización.

**Pasos:**

1. Haga clic en **"Nueva Categoría"**.

2. Ingrese los datos:
   - **Nombre:** Ej. Entradas, Bebidas, Postres.
   - **Descripción (opcional):** Información sobre la categoría.
   - **Orden de visualización:** Prioridad para mostrar en el menú digital.

3. Presione **Guardar**.

La nueva categoría aparecerá en el panel y podrá agregar productos dentro de ella.

## 4. Agregar productos

1. Seleccione la categoría deseada.

2. Haga clic en **"Nuevo Producto"**.

3. Complete los campos obligatorios:
   - **Nombre del producto:** Ej. Hamburguesa Clásica.
   - **Código interno / product_id** (único dentro del restaurante).
   - **Precio bruto** (antes de impuestos).
   - **Disponibilidad por turno:** Desayuno, Almuerzo, Cena.
   - **Opciones adicionales (opcional):** Por ejemplo, ingredientes extra, salsas, tamaño.

4. Guarde los cambios. El producto aparecerá en la lista de la categoría correspondiente.

## 5. Editar o eliminar productos

- **Para editar**, haga clic en el producto → **Editar**.  
  Se pueden modificar nombre, precio, opciones o disponibilidad.

- **Para eliminar**, haga clic en **Eliminar** → **Confirmar**.

⚠️ **Importante:** No se puede eliminar un producto que esté asociado a órdenes activas.  
Primero cierre o transfiera las órdenes correspondientes.

## 6. Configuración de impuestos y descuentos

GastroSoft POS permite calcular automáticamente los impuestos y aplicar descuentos según reglas predefinidas.

Desde la pestaña de **Configuración de producto → Impuestos:**

- Seleccione el porcentaje aplicable (Ej. 10 %, 19 %).
- Configure impuestos locales o especiales según el producto.

Para descuentos:

- Puede aplicar por producto, categoría o total de orden.
- Defina el tipo: fijo o porcentaje.

## 7. Opciones avanzadas y modificadores

Algunos productos requieren personalización adicional:

- **Modificadores:** Permiten elegir variantes de un producto (Ej. tamaño, toppings, acompañamientos).
- **Extras:** Ingredientes adicionales que aumentan el precio.
- **Disponibilidad limitada:** Puede activar/desactivar productos según horario o stock.

💡 **Tip:** Cree un conjunto de modificadores reutilizable para productos similares.

## 8. Importación y exportación de menús

- **Exportar menú completo:** Obtenga un CSV con todas las categorías y productos para respaldo o edición masiva.
- **Importar menú:** Permite subir un archivo CSV siguiendo la plantilla de GastroSoft POS.

Evite duplicar product_id al importar desde otro restaurante.

## 9. Buenas prácticas

- Mantenga nombres claros y consistentes.
- Defina precios y opciones antes de abrir operaciones.
- Use la disponibilidad por turno para automatizar horarios de productos.
- Revise periódicamente los modificadores y extras para evitar confusiones al mesero.

## 10. Solución de problemas comunes

| Problema | Posible causa | Solución |
|----------|---------------|----------|
| Producto no aparece en el menú | No está asignado a ninguna categoría | Asigne el producto a la categoría correspondiente |
| Error al guardar producto | product_id duplicado | Cree un product_id único dentro del restaurante |
| No se aplican impuestos | Configuración incorrecta del impuesto | Revise la pestaña de impuestos y asegúrese que el porcentaje es correcto |
| Modificador no se muestra en POS | No está habilitado | Active el modificador y asocie al producto |