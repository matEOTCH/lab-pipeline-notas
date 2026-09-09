# Labs Notas

> **Proyecto en desarrollo activo.** El flujo base (generar lista, crear grupos, subir notas) ya funciona; se estan incorporando funciones nuevas como el registro de bajas de estudiantes y grupos fijos importados desde Blackboard.

Herramienta para el curso de **Quimica General** que automatiza tres tareas repetitivas del laboratorio:

1. Limpiar la lista de un curso exportada de Blackboard.
2. Armar los grupos de laboratorio (con PDF, CSVs listos para importar a Blackboard, y un zip descargable).
3. Subir notas a un unico workbook de seguimiento ("Notas"), incluyendo resultados de TeamMates, notas manuales/por archivo, y marcado de ausentes.

Todo corre contra archivos `.xlsx` guardados en Google Drive (via `openpyxl`), pensado para ejecutarse desde **Google Colab** — no usa la API de Google Sheets ni requiere credenciales propias.

## Estructura de carpetas (en Google Drive)

```
<workspace>/                          # Mi unidad, o el directorio actual fuera de Colab
  <proyecto>/                         # p.ej. "2026"
    <curso ciclo>/                    # p.ej. "Quimica General 2026-1"
      Lista/<seccion>-Lista.xlsx                          # lista limpia del curso
      Notas/<seccion>-Notas-Laboratorios.xlsx              # gradebook con notas y grupos
      Grupos Laboratorio/<seccion>/Laboratorio <n>/...     # PDF + CSVs + zip por laboratorio
      Bajas/<seccion>-Lista-Bajas.xlsx                      # (en desarrollo) estudiantes dados de baja
      Bajas/<seccion>-Notas-Laboratorios-Bajas.xlsx
```

## Como usarlo: `Lab_Main_Pipeline.ipynb`

Este es el notebook principal y la guia de uso recomendada. Los demas notebooks del paquete (`Lab_App_Colab_UI.ipynb`, `Generar_Estructura.ipynb`, `Lab_Group_Manager.ipynb`, `Import_Teammates_to_Notas.ipynb`) son variantes/legado que terminan llamando al mismo codigo de `lab_pipeline/` — para empezar, usa `Lab_Main_Pipeline.ipynb`.

1. **Load Package** (celda 1): monta Google Drive (si estas en Colab) y carga el paquete `lab_pipeline`. Se corre siempre, al inicio de cada sesion.
2. **Actualizar Paquete** (celda 2, opcional): solo si tienes una version nueva de `lab_pipeline_package.zip` para subir.
3. **Choose Route** (celda 3): elige una de las tres opciones del menu.

### Opcion 1 - Generar estructura

Crea las carpetas del curso/ciclo y convierte el CSV de actividad de curso exportado de Blackboard en la lista limpia (`Lista/<seccion>-Lista.xlsx`). Se corre una vez por seccion, al inicio del ciclo.

### Opcion 2 - Crear Grupos de Laboratorio

Lee la lista de la seccion, sortea (o asigna) los estudiantes en grupos, y genera:

- La columna `Grupo_LabN` en el workbook de Notas.
- Un PDF con los grupos.
- CSVs de grupos y miembros listos para importar a Blackboard.
- Un zip con los tres archivos.

### Opcion 3 - Subiendo notas

Sube/actualiza en el workbook de Notas:

- Resultados de TeamMates (porcentaje y si respondieron la evaluacion de pares).
- Notas adicionales por laboratorio, con tres metodos de carga: archivo de Blackboard, ingreso manual por alumno, o ingreso manual por grupo.
- Marcado de estudiantes ausentes (pone en cero sus columnas de esa practica).

**Cursos sin "compañeros de equipo" (TeamMates):** esta opcion ya funciona sin ellos. Cuando pregunte *"¿Desea subir/actualizar informacion de Teammates?"*, responde que no. Para las notas, usa el metodo **"Ingreso manual por alumno"** (no depende de que existan grupos ni de haber corrido la Opcion 2). Solo el metodo "Ingreso manual por grupo" requiere haber creado grupos antes.

## Tests

```
cd lab_pipeline_package
pytest
```
