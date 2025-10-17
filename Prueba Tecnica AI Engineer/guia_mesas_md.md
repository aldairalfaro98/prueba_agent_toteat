# Guía Técnica 1 — Configuración de Mesas y Áreas

**Software:** GastroSoft POS  
**Versión:** 2.1.5 (enero 2025)  
**Documento técnico** — Configuración inicial de mesas, áreas y distribución de sala.

## 1. Introducción

La correcta configuración de mesas y áreas en GastroSoft POS permite optimizar la operación del restaurante, asignar pedidos correctamente y mejorar el seguimiento de la atención.

Cada mesa pertenece a un área (por ejemplo, Salón principal, Terraza, Barra), y puede tener atributos personalizados como capacidad, estado y prioridad de servicio.

Este documento describe el proceso para crear, editar y gestionar las mesas dentro del sistema.

## 2. Acceso al módulo de configuración

1. Inicie sesión en su cuenta de GastroSoft POS con un perfil de **Administrador** o **Gerente**.

2. En el menú lateral izquierdo, seleccione:  
   **Configuración → Áreas y Mesas**.

3. Se abrirá el panel principal, donde podrá ver las áreas existentes y su disposición gráfica de mesas.

## 3. Crear un área nueva

Las áreas permiten agrupar mesas según su ubicación física o funcional.

**Pasos:**

1. Haga clic en **"Nueva Área"**.

2. Ingrese los datos solicitados:
   - **Nombre del área:** Ej. Salón Principal, Terraza.
   - **Color de identificación:** Este color se muestra en el mapa.
   - **Capacidad total (opcional):** cantidad estimada de asientos.

3. Presione **Guardar**.

Una vez creada el área, aparecerá en la barra lateral con un color asignado y podrá agregarle mesas.

## 4. Agregar mesas a un área

Desde el panel de áreas:

1. Seleccione el área deseada.

2. Haga clic en **"Agregar Mesa"**.

3. En el modal emergente:
   - **Número de mesa:** debe ser único dentro del área.
   - **Capacidad:** cantidad de personas.
   - **Tipo:** estándar, barra, VIP, etc.
   - **Estado inicial:** libre / ocupada / reservada.

4. Pulse **Guardar**.

La mesa se mostrará en el mapa con un ícono circular o cuadrado, dependiendo del tipo.

## 5. Editar o eliminar mesas existentes

- **Para editar**, haga clic sobre la mesa en el mapa → **Editar mesa**.  
  Puede cambiar el nombre, capacidad o posición arrastrando el ícono.

- **Para eliminar**, seleccione la mesa → **Eliminar mesa** → **Confirmar**.

⚠️ **Importante:** No puede eliminar una mesa con órdenes activas.  
Deberá cerrar o transferir las órdenes antes de borrarla.

## 6. Organización del mapa

Puede reorganizar visualmente las mesas para que el plano refleje la disposición real del local.

- **Arrastrar y soltar:** mueve la posición de la mesa.
- **Zoom in/out:** ajusta la vista del plano.
- **Alinear mesas:** seleccione varias y use la opción "Alinear en fila/columna".
- **Mostrar etiquetas:** activa/desactiva números o nombres de mesa.

## 7. Asignar meseros por área

Cada área puede tener uno o varios meseros responsables.

1. Vaya a **Configuración → Áreas y Mesas → Asignación de Personal**.

2. Seleccione el área y elija los usuarios con rol **Mesero**.

3. Guarde los cambios.

El sistema reflejará automáticamente los meseros asignados cuando se creen órdenes en esa área.

## 8. Estados de mesa

Los estados posibles de una mesa son:

| Estado    | Descripción                      | Color en interfaz |
|-----------|----------------------------------|-------------------|
| Libre     | Disponible para asignar una orden| Verde             |
| Ocupada   | Tiene una orden activa           | Rojo              |
| Reservada | Asignada a una reserva futura    | Amarillo          |
| Cerrada   | La orden fue cerrada recientemente| Gris             |