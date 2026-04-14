from flask import send_file
from models import Ciclo, Estudiante, Supervisor, Grupo, Reporte, estudiante_grupo
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from extensions import db, migrate
import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from sqlalchemy.orm import joinedload

def generar_pdf_grupos(grupos, titulo="Reporte de Grupos"):
    """Función auxiliar para generar un PDF con una lista de grupos en formato horizontal."""
    buf = BytesIO()
    
    # --- CAMBIO CLAVE: Usar landscape(A4) para poner la página acostada ---
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    story = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CustomTitle', fontSize=18, parent=styles['Heading1'], spaceAfter=30))
    
    # Título
    story.append(Paragraph(titulo, styles['CustomTitle']))
    story.append(Spacer(1, 12))

    for grupo in grupos:
        # Datos del grupo
        data_grupo = [
            ['Ciclo:', f'{grupo.ciclo.nombre} ({grupo.ciclo.anio})'],
            ['Lugar:', grupo.lugar],
            ['Fechas:', f'{grupo.fecha_inicio.strftime("%d/%m/%Y")} al {grupo.fecha_fin.strftime("%d/%m/%Y")}'],
            ['Modalidad:', grupo.modalidad.capitalize()],
            ['Supervisor:', f'{grupo.supervisor.nombre} {grupo.supervisor.apellido}'],
        ]
        tabla_grupo = Table(data_grupo, colWidths=[1.5 * inch, 4 * inch])
        tabla_grupo.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(tabla_grupo)
        story.append(Spacer(1, 12))

        # Listado de estudiantes
        story.append(Paragraph("Estudiantes Asignados:", styles['Heading2']))
        
        # --- CAMBIO 1: Añadir la nueva columna "Estado de Pago" al encabezado ---
        data_estudiantes = [['Carnet', 'Nombre', 'Semestre', 'Sección', 'Estado Académico', 'Estado de Pago']]
        
        for est in grupo.estudiantes:
            # --- CAMBIO 2: Añadir la lógica para el estado de pago ---
            estado_pago_texto = "Pendiente"
            if est.fecha_pago:
                # Si tiene fecha de pago, muestra "Pagado" y la fecha
                estado_pago_texto = f"Pagado ({est.fecha_pago.strftime('%d/%m/%Y')})"

            data_estudiantes.append([
                est.carnet, 
                est.nombre, 
                est.semestre, 
                est.seccion, 
                est.estado_academico,
                estado_pago_texto  # <-- Aquí se añade el nuevo dato
            ])
        
        # --- CAMBIO 3: Ajustar los anchos de columna para la nueva columna ---
        # Se redujo un poco el ancho de "Nombre" y "Estado Académico" para hacer espacio.
        tabla_estudiantes = Table(data_estudiantes, hAlign='LEFT', colWidths=[0.9*inch, 3.8*inch, 1.0*inch, 1.0*inch, 1.6*inch, 1.4*inch])
        tabla_estudiantes.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla_estudiantes)
        story.append(Spacer(1, 20))
        
    doc.build(story)
    buf.seek(0)
    return buf

def create_app():
    """
    Función Fábrica de la Aplicación Flask.
    Crea y configura la instancia de la aplicación.
    """
    # --- Creación de la instancia de Flask ---
    app = Flask(__name__)

    # --- Configuración de la aplicación ---
    from config import Config
    app.config.from_object(Config)

    # --- Inicialización de las extensiones con la aplicación ---
    db.init_app(app)
    migrate.init_app(app, db)

    # --- Registrar rutas ---
    # Ya no necesitamos importar los modelos aquí.
    register_routes(app)

    return app


def register_routes(app):
    """
    Función para registrar todas las rutas.
    """
    
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/estudiantes/<int:id_ciclo>')
    def get_estudiantes_por_ciclo(id_ciclo):
        """API para obtener estudiantes de un ciclo específico en formato JSON."""
        estudiantes = Estudiante.query.filter_by(id_ciclo=id_ciclo).order_by(Estudiante.nombre).all()
        # Devolvemos los datos de forma estructurada para la tabla
        lista_estudiantes = [{'id': est.id, 'carnet': est.carnet, 'nombre': est.nombre} for est in estudiantes]
        return jsonify(lista_estudiantes)
    
    @app.route('/api/estudiante/<int:id_estudiante>/actualizar_estado', methods=['POST'])
    def actualizar_estado_estudiante(id_estudiante):
        """API para actualizar el estado académico de un estudiante."""
        estudiante = Estudiante.query.get_or_404(id_estudiante)
        data = request.get_json()
        nuevo_estado = data.get('estado')
        if not nuevo_estado:
            return jsonify({"status": "error", "message": "El nuevo estado no puede estar vacío."}), 400
        try:
            estudiante.estado_academico = nuevo_estado
            db.session.commit()
            return jsonify({"status": "success", "message": "Estado académico actualizado correctamente."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Error al actualizar el estado: {e}"}), 500
        
    @app.route('/api/estudiante/<int:id_estudiante>/registrar_pago', methods=['POST'])
    def registrar_pago_api(id_estudiante):
        """API para registrar el pago de un estudiante desde un modal."""
        estudiante = Estudiante.query.get_or_404(id_estudiante)
        data = request.get_json()
        fecha_str = data.get('fecha_pago')
        
        if not fecha_str:
            return jsonify({"status": "error", "message": "La fecha de pago no puede estar vacía."}), 400

        # Si el estudiante ya tiene un pago registrado, no hacer nada
        if estudiante.fecha_pago:
            return jsonify({"status": "info", "message": "Este estudiante ya tiene un pago registrado."}), 200

        try:
            estudiante.fecha_pago = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            db.session.commit()
            return jsonify({"status": "success", "message": "Pago registrado exitosamente."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Error al registrar el pago: {e}"}), 500
        
    @app.route('/ciclos', methods=['GET', 'POST'])
    def gestionar_ciclos():
        if request.method == 'POST':
            nuevo_ciclo = Ciclo(
                nombre=request.form['nombre'],
                fecha_inicio=datetime.datetime.strptime(
                    request.form.get('fecha_inicio'), '%Y-%m-%d').date(),
                fecha_fin=datetime.datetime.strptime(
                    request.form['fecha_fin'], '%Y-%m-%d').date(),
                anio=int(request.form['anio'])
            )
            db.session.add(nuevo_ciclo)
            try:
                db.session.commit()
                flash('Ciclo creado exitosamente.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear el ciclo: {e}', 'danger')
            return redirect(url_for('gestionar_ciclos'))

        ciclos = Ciclo.query.order_by(Ciclo.anio.desc()).all()
        return render_template('ciclos/lista_ciclos.html', ciclos=ciclos)

    # --- Módulo 2: Carga de Estudiantes ---
    @app.route('/ciclo/<int:id_ciclo>/estudiantes', methods=['GET', 'POST'])
    def gestionar_estudiantes(id_ciclo):
        ciclo = Ciclo.query.get_or_404(id_ciclo)
        
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No se seleccionó ningún archivo.', 'warning')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No se seleccionó ningún archivo.', 'warning')
                return redirect(request.url)

            if file and file.filename.endswith('.xlsx'):
                try:
                    # CAMBIO: Leer columnas C y D. El índice empieza en 0.
                    # C=2, D=3. A y B son 0 y 1.
                    df = pd.read_excel(file, skiprows=1, header=None, names=['carnet', 'nombre', 'semestre', 'seccion'])
                    df.dropna(inplace=True)
                    
                    nuevos_estudiantes = []
                    for index, row in df.iterrows():
                        existe = Estudiante.query.filter_by(carnet=row['carnet'], id_ciclo=id_ciclo).first()
                        if not existe:
                            nuevos_estudiantes.append(
                                Estudiante(
                                    carnet=str(row['carnet']), 
                                    nombre=row['nombre'], 
                                    semestre=str(row['semestre']),
                                    seccion=str(row['seccion']),
                                    id_ciclo=id_ciclo
                                )
                            )
                    
                    if nuevos_estudiantes:
                        db.session.add_all(nuevos_estudiantes)
                        db.session.commit()
                        flash(f'Se cargaron {len(nuevos_estudiantes)} estudiantes nuevos.', 'success')
                    else:
                        flash('Todos los estudiantes del archivo ya existen en este ciclo.', 'info')

                except Exception as e:
                    db.session.rollback()
                    flash(f'Error al procesar el archivo: {e}', 'danger')
            else:
                flash('Formato de archivo no válido. Por favor, sube un archivo .xlsx', 'danger')
            
            return redirect(url_for('gestionar_estudiantes', id_ciclo=id_ciclo))

        estudiantes = Estudiante.query.filter_by(id_ciclo=id_ciclo).order_by(Estudiante.nombre).all()
        return render_template('estudiantes/lista_estudiantes.html', ciclo=ciclo, estudiantes=estudiantes)

    @app.route('/supervisores', methods=['GET', 'POST'])
    def gestionar_supervisores():
        if request.method == 'POST':
            nuevo_supervisor = Supervisor(
                nombre=request.form['nombre'],
                apellido=request.form['apellido'],
                telefono=request.form['telefono'],
                correo=request.form['correo']
            )
            db.session.add(nuevo_supervisor)
            try:
                db.session.commit()
                flash('Supervisor agregado exitosamente.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al agregar supervisor: {e}', 'danger')
            return redirect(url_for('gestionar_supervisores'))

        supervisores = Supervisor.query.order_by(Supervisor.nombre).all()
        return render_template('supervisores/lista_supervisores.html', supervisores=supervisores)

    @app.route('/grupos', methods=['GET', 'POST'])
    def gestionar_grupos():
        if request.method == 'POST':
            # ... (El código POST permanece exactamente igual) ...
            id_supervisor = request.form.get('id_supervisor')
            id_ciclo = request.form.get('id_ciclo')
            lugar = request.form.get('lugar')
            fecha_inicio = datetime.datetime.strptime(request.form.get('fecha_inicio'), '%Y-%m-%d').date()
            fecha_fin = datetime.datetime.strptime(request.form.get('fecha_fin'), '%Y-%m-%d').date()
            modalidad = request.form.get('modalidad')
            tipo_pago = request.form.get('tipo_pago', '20_turnos')
            estudiantes_seleccionados_ids = request.form.getlist('estudiantes')

            # --- CAMBIO: Se elimina el límite superior de 10 estudiantes ---
            if len(estudiantes_seleccionados_ids) < 1:
                flash('El grupo debe tener al menos 1 estudiante.', 'danger')
                return redirect(url_for('gestionar_grupos'))

            grupos_conflicto = Grupo.query.filter(
                Grupo.id_supervisor == id_supervisor,
                Grupo.modalidad == modalidad,
                Grupo.fecha_inicio <= fecha_fin,
                Grupo.fecha_fin >= fecha_inicio
            ).count()
            
            if grupos_conflicto >= 1:
                flash(f'El supervisor ya tiene un grupo asignado en la misma jornada ({modalidad}) en estas fechas.', 'danger')
                return redirect(url_for('gestionar_grupos'))

            estudiantes_obj = Estudiante.query.filter(Estudiante.id.in_(estudiantes_seleccionados_ids)).all()
            for estudiante in estudiantes_obj:
                grupos_del_estudiante = Grupo.query.filter(
                    Grupo.estudiantes.any(id=estudiante.id),
                    Grupo.fecha_inicio <= fecha_fin,
                    Grupo.fecha_fin >= fecha_inicio
                ).all()
                if grupos_del_estudiante:
                    nombres_grupos_conflicto = ", ".join([g.lugar for g in grupos_del_estudiante])
                    flash(f'El estudiante {estudiante.nombre} ya está asignado a otro grupo en estas fechas: {nombres_grupos_conflicto}.', 'danger')
                    return redirect(url_for('gestionar_grupos'))

            try:
                nuevo_grupo = Grupo(
                    lugar=lugar,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    modalidad=modalidad,
                    id_supervisor=id_supervisor,
                    id_ciclo=id_ciclo,
                    tipo_pago=tipo_pago
                )
                db.session.add(nuevo_grupo)
                db.session.flush()

                nuevo_grupo.estudiantes = estudiantes_obj
                
                db.session.commit()
                flash('Grupo de práctica creado exitosamente.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear el grupo: {e}', 'danger')
            
            return redirect(url_for('gestionar_grupos'))

        # --- INICIO DEL BLOQUE MODIFICADO ---
        # 1. Mejora la consulta para cargar los supervisores de una vez y evitar múltiples consultas a la BD
        all_grupos = Grupo.query.options(joinedload(Grupo.supervisor)).all()
        grupos_activos = []
        hoy = datetime.date.today()

        for grupo in all_grupos:
            # Si el grupo no ha finalizado, siempre se muestra
            if grupo.fecha_fin >= hoy:
                grupos_activos.append(grupo)
            else:
                # Si ya finalizó, calculamos las fechas pendientes
                all_dates = set()
                current_date = grupo.fecha_inicio
                while current_date <= grupo.fecha_fin:
                    if current_date.weekday() < 5:
                        all_dates.add(current_date)
                    current_date += datetime.timedelta(days=1)
                
                reportes_existentes = Reporte.query.filter_by(id_grupo=grupo.id).all()
                registered_dates = {r.fecha_turno for r in reportes_existentes}
                
                unregistered_dates = all_dates - registered_dates
                
                # Si aún quedan fechas por procesar, el grupo se mantiene activo
                if unregistered_dates:
                    grupos_activos.append(grupo)

        # 2. ORDENA LA LISTA DE GRUPOS ACTIVOS
        # Ordena por: 1) Fecha de inicio (descendente), 2) Nombre del supervisor (ascendente), 3) Lugar (ascendente)
        grupos_activos = sorted(
            grupos_activos, 
            key=lambda g: (g.fecha_inicio.toordinal(), g.supervisor.nombre_completo(), g.lugar)
        )
        # --- FIN DEL BLOQUE MODIFICADO ---

        # El resto del código GET no cambia, solo pasamos la lista filtrada y ya ordenada
        supervisores = Supervisor.query.order_by(Supervisor.nombre).all()
        ciclos = Ciclo.query.order_by(Ciclo.anio.desc()).all()
        estudiantes = Estudiante.query.order_by(Estudiante.nombre).all()
        return render_template('grupos/lista_grupos.html', 
                            grupos=grupos_activos, 
                            supervisores=supervisores, 
                            ciclos=ciclos,
                            estudiantes=estudiantes)

    # --- Módulo Extra: Buscador de Estudiantes ---
    @app.route('/buscar_estudiante', methods=['GET', 'POST'])
    def buscar_estudiante():
        estudiantes_encontrados = []
        search_term = ""
        
        if request.method == 'POST':
            search_term = request.form.get('search_term', '').strip()
            if search_term:
                # Crea el patrón de búsqueda para 'LIKE' en SQL (ej: '%juan%')
                search_pattern = f'%{search_term}%'
                
                # Busca estudiantes donde el nombre o el carnet coincidan (ignorando mayúsculas/minúsculas)
                # Usamos 'ilike' para una búsqueda insensible a mayúsculas.
                # Limitamos a 50 resultados para no sobrecargar la página.
                query = Estudiante.query.filter(
                    (Estudiante.nombre.ilike(search_pattern)) | 
                    (Estudiante.carnet.ilike(search_pattern))
                )
                estudiantes_encontrados = query.limit(50).all()

        # Renderiza la plantilla, pasándole los resultados y el término buscado
        return render_template('buscar_estudiante.html', estudiantes=estudiantes_encontrados, search_term=search_term)

    @app.route('/grupo/<int:id>/editar', methods=['GET', 'POST'])
    def editar_grupo(id):
        grupo = Grupo.query.get_or_404(id)
        if request.method == 'POST':
            grupo.id_supervisor = request.form.get('id_supervisor')
            grupo.lugar = request.form.get('lugar')
            grupo.fecha_inicio = datetime.datetime.strptime(request.form.get('fecha_inicio'), '%Y-%m-%d').date()
            grupo.fecha_fin = datetime.datetime.strptime(request.form.get('fecha_fin'), '%Y-%m-%d').date()
            modalidad = request.form.get('modalidad')
            grupo.modalidad = modalidad
            grupo.tipo_pago = request.form.get('tipo_pago', '20_turnos')
            estudiantes_seleccionados_ids = request.form.getlist('estudiantes')

            # --- CAMBIO: Se elimina el límite superior de 10 estudiantes ---
            if len(estudiantes_seleccionados_ids) < 1:
                flash('El grupo debe tener al menos 1 estudiante.', 'danger')
                return redirect(url_for('editar_grupo', id=id))
            
            # Excluimos el grupo actual de la búsqueda y comprobamos la modalidad
            grupos_conflicto = Grupo.query.filter(
                Grupo.id != id,  # <-- Excluir el grupo actual
                Grupo.id_supervisor == grupo.id_supervisor,
                Grupo.modalidad == modalidad,
                Grupo.fecha_inicio <= grupo.fecha_fin,
                Grupo.fecha_fin >= grupo.fecha_inicio
            ).count()

            if grupos_conflicto >= 1: 
                flash(f'El supervisor ya tiene un grupo asignado en la misma jornada ({modalidad}) en estas fechas.', 'danger')
                return redirect(url_for('editar_grupo', id=id))

            # Lógica de detección de conflictos de estudiantes (sin cambios)
            estudiantes_obj = Estudiante.query.filter(Estudiante.id.in_(estudiantes_seleccionados_ids)).all()
            for estudiante in estudiantes_obj:
                grupos_del_estudiante = Grupo.query.filter(
                    Grupo.id != id,
                    Grupo.estudiantes.any(id=estudiante.id),
                    Grupo.fecha_inicio <= grupo.fecha_fin,
                    Grupo.fecha_fin >= grupo.fecha_inicio
                ).all()
                if grupos_del_estudiante:
                    nombres_grupos_conflicto = ", ".join([g.lugar for g in grupos_del_estudiante])
                    flash(f'El estudiante {estudiante.nombre} ya está asignado a otro grupo en estas fechas: {nombres_grupos_conflicto}.', 'danger')
                    return redirect(url_for('editar_grupo', id=id))
            
            try:
                grupo.estudiantes = estudiantes_obj

                # --- NUEVA LÓGICA: Actualizar pagos de turnos no pagados ---
                # Obtenemos todos los reportes (turnos) de este grupo que aún no han sido pagados.
                reportes_pendientes_actualizar = Reporte.query.filter_by(id_grupo=grupo.id, pagado=False).all()

                # Recorremos cada reporte pendiente
                for reporte in reportes_pendientes_actualizar:
                    # Calculamos el nuevo monto usando el método del grupo ya actualizado en memoria
                    nuevo_pago = grupo.calcular_pago_por_turno()
                    # Fijamos el nuevo valor en el reporte
                    reporte.pago_turno_fijado = nuevo_pago
                # --- FIN DE LA NUEVA LÓGICA ---

                db.session.commit()
                # He actualizado el mensaje flash para que sea más informativo
                flash('Grupo actualizado exitosamente. Los pagos pendientes han sido recalculados.', 'success')
                return redirect(url_for('gestionar_grupos'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar el grupo: {e}', 'danger')

        # El resto de la función GET no cambia
        supervisores = Supervisor.query.order_by(Supervisor.nombre).all()
        ciclos = Ciclo.query.order_by(Ciclo.anio.desc()).all()
        estudiantes = Estudiante.query.filter_by(id_ciclo=grupo.id_ciclo).order_by(Estudiante.nombre).all()
        return render_template('grupos/editar_grupo.html', grupo=grupo, supervisores=supervisores, estudiantes=estudiantes, ciclos=ciclos)

    @app.route('/grupo/<int:id>/eliminar', methods=['POST'])
    def eliminar_grupo(id):
        grupo = Grupo.query.get_or_404(id)
        try:
            db.session.delete(grupo)
            db.session.commit()
            flash('Grupo y sus reportes han sido eliminados.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el grupo: {e}', 'danger')
        return redirect(url_for('gestionar_grupos'))

    # --- Módulo 6: Registro de Reportes ---
    @app.route('/reportes/registrar')
    def registrar_reportes():
        """Muestra el listado de grupos para elegir cuál registrar."""
        grupos = Grupo.query.order_by(Grupo.lugar).all()
        return render_template('reportes/lista_grupos_para_registro.html', grupos=grupos)

    @app.route('/reportes/registrar/<int:id_grupo>', methods=['GET', 'POST'])
    def registrar_turnos_grupo(id_grupo):
        """Muestra las fechas faltantes de un grupo y permite registrarlas."""
        grupo = Grupo.query.get_or_404(id_grupo)

        if request.method == 'POST':
            fechas_a_registrar_str = request.form.getlist('fechas_a_registrar')
            for fecha_str in fechas_a_registrar_str:
                fecha_turno = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
                nuevo_reporte = Reporte(
                    id_grupo=grupo.id,
                    id_supervisor=grupo.id_supervisor,
                    fecha_turno=fecha_turno
                )
                db.session.add(nuevo_reporte)
            
            try:
                db.session.commit()
                flash(f'Se registraron {len(fechas_a_registrar_str)} turnos exitosamente.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al registrar los turnos: {e}', 'danger')
            
            return redirect(url_for('registrar_turnos_grupo', id_grupo=id_grupo))

        # --- Lógica para GET ---
        all_dates = set()
        current_date = grupo.fecha_inicio
        while current_date <= grupo.fecha_fin:
            if current_date.weekday() < 5: # Solo días de lunes a viernes
                all_dates.add(current_date)
            current_date += datetime.timedelta(days=1)
        
        reportes_existentes = Reporte.query.filter_by(id_grupo=id_grupo).order_by(Reporte.fecha_turno.asc()).all()
        registered_dates = {r.fecha_turno for r in reportes_existentes}
        
        unregistered_dates = sorted(list(all_dates - registered_dates))
        
        # --- NUEVO: Formateador de fechas en español (sin usar locale) ---
        SPANISH_DAYS = {
            0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
        }
        SPANISH_MONTHS = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
            7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        def format_date_spanish(d):
            """Formatea un objeto de fecha a un string en español."""
            return f"{SPANISH_DAYS[d.weekday()]}, {d.day} de {SPANISH_MONTHS[d.month]} de {d.year}"

        unregistered_dates_formatted = [
            {'date_obj': d, 'date_str': format_date_spanish(d)} for d in unregistered_dates
        ]
        
        reportes_existentes_formatted = [
            {'id': r.id, 'date_str': format_date_spanish(r.fecha_turno)} for r in reportes_existentes
        ]
        
        return render_template('reportes/registrar_turnos_grupo.html', 
                            grupo=grupo, 
                            unregistered_dates=unregistered_dates_formatted,
                            reportes_existentes=reportes_existentes_formatted)

    @app.route('/reportes/eliminar/<int:id_reporte>', methods=['POST'])
    def eliminar_reporte(id_reporte):
        """Elimina un registro de turno específico."""
        reporte = Reporte.query.get_or_404(id_reporte)
        id_grupo = reporte.id_grupo
        try:
            db.session.delete(reporte)
            db.session.commit()
            flash('Turno eliminado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el turno: {e}', 'danger')
        
        return redirect(url_for('registrar_turnos_grupo', id_grupo=id_grupo))

    @app.route('/reportes/pagos')
    def reporte_pagos():
        supervisores = Supervisor.query.order_by(Supervisor.apellido).all()
        datos_reporte = []
        
        for sup in supervisores:
            # --- CAMBIO CLAVE: La consulta ahora filtra por pagado=False
            reportes_pendientes = Reporte.query.filter_by(id_supervisor=sup.id, pagado=False).order_by(Reporte.fecha_turno.desc()).all()
            
            if reportes_pendientes:
                pagos_mensuales = {}
                total_general = 0
                
                for reporte in reportes_pendientes:
                    try:
                        # --- MEJORA: Calcula el pago si no está fijado ---
                        if reporte.pago_turno_fijado is not None:
                            pago_turno = float(reporte.pago_turno_fijado)
                        else:
                            # Calcula el pago usando el método del modelo Grupo
                            pago_turno = reporte.grupo.calcular_pago_por_turno()
                    except Exception as e:
                        print(f"Error: No se pudo obtener el pago para el reporte {reporte.id}. Error: {e}")
                        continue
                    
                    mes = reporte.fecha_turno.strftime('%Y-%m')
                    if mes not in pagos_mensuales:
                        pagos_mensuales[mes] = {'mes': mes, 'cantidad_turnos': 0, 'total_pago': 0, 'reportes': []}
                    
                    pagos_mensuales[mes]['cantidad_turnos'] += 1
                    pagos_mensuales[mes]['total_pago'] += pago_turno
                    total_general += pago_turno
                    pagos_mensuales[mes]['reportes'].append(reporte)
                
                if pagos_mensuales:
                    datos_reporte.append({
                        'supervisor': sup.nombre_completo(),
                        'pagos': list(pagos_mensuales.values()),
                        'total_general': round(total_general, 2)
                    })
                    
        if datos_reporte:
            return render_template('reportes/reporte_pagos.html', datos_reporte=datos_reporte)
        else:
            return render_template('reportes/reporte_pagos.html', datos_reporte={})
    
    @app.route('/reportes/historial_pagos')
    def historial_pagos():
        supervisores = Supervisor.query.order_by(Supervisor.apellido).all()
        datos_historial = []
        
        for sup in supervisores:
            reportes_pagados = Reporte.query.filter_by(id_supervisor=sup.id, pagado=True).order_by(Reporte.fecha_turno.desc()).all()
            if reportes_pagados:
                ciclos_dict = {}
                for reporte in reportes_pagados:
                    ciclo = reporte.grupo.ciclo
                    if ciclo.nombre not in ciclos_dict:
                        ciclos_dict[ciclo.nombre] = {'ciclo_obj': ciclo, 'reportes': []}
                    ciclos_dict[ciclo.nombre]['reportes'].append(reporte)

                # Convertimos el diccionario a una lista ordenada por año de ciclo
                ciclos_list = sorted(ciclos_dict.values(), key=lambda x: x['ciclo_obj'].anio, reverse=True)
                
                datos_historial.append({
                    'supervisor': sup.nombre_completo(),
                    'ciclos': ciclos_list
                })
                
        return render_template('reportes/historial_pagos.html', datos_historial=datos_historial)
    
    @app.route('/api/reporte/<int:id_reporte>/marcar_pagado', methods=['POST'])
    def marcar_turno_pagado(id_reporte):
        reporte = Reporte.query.get_or_404(id_reporte)
        if reporte.pagado:
            return jsonify({"status": "error", "message": "Este turno ya estaba marcado como pagado."}), 400
        
        try:
            # Calcular el pago actual y fijarlo
            pago_actual = reporte.grupo.calcular_pago_por_turno()
            reporte.pago_turno_fijado = pago_actual
            reporte.pagado = True
            db.session.commit()
            return jsonify({"status": "success", "message": "Turno marcado como pagado correctamente."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Error al marcar el pago: {e}"}), 500

    @app.route('/api/turno/<int:id_grupo>/procesar', methods=['POST'])
    def procesar_accion_turno(id_grupo):
        """API para registrar, marcar como feriado o no dado un turno."""
        data = request.get_json()
        fecha_str = data.get('fecha')
        accion = data.get('accion') # 'registrar', 'feriado', 'no_dio'

        if not all([fecha_str, accion]):
            return jsonify({"status": "error", "message": "Faltan datos para procesar la acción."}), 400

        fecha_turno = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        grupo = Grupo.query.get_or_404(id_grupo)

        reporte_existente = Reporte.query.filter_by(id_grupo=id_grupo, fecha_turno=fecha_turno).first()
        if reporte_existente:
            return jsonify({"status": "error", "message": "Este turno ya ha sido procesado anteriormente."}), 400

        # Necesitamos el formateador de fechas español
        SPANISH_DAYS = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
        SPANISH_MONTHS = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
        def format_date_spanish(d): return f"{SPANISH_DAYS[d.weekday()]}, {d.day} de {SPANISH_MONTHS[d.month]} de {d.year}"
        pago_turno = grupo.calcular_pago_por_turno()

        try:
            nuevo_reporte = Reporte(
                id_grupo=id_grupo,
                id_supervisor=grupo.id_supervisor,
                fecha_turno=fecha_turno,
                estado='realizado',
                pagado=False,
                pago_turno_fijado=pago_turno
            )

            if accion == 'registrar': pass
            elif accion == 'feriado':
                nuevo_reporte.estado = 'feriado'
                nuevo_reporte.pagado = True
                nuevo_reporte.pago_turno_fijado = 0.0
            elif accion == 'no_dio':
                nuevo_reporte.estado = 'no se dio' # Usamos 'no se dio' para que se vea bien
                nuevo_reporte.pagado = True
                nuevo_reporte.pago_turno_fijado = 0.0
            else:
                return jsonify({"status": "error", "message": "Acción no válida."}), 400

            db.session.add(nuevo_reporte)
            db.session.commit()
            
            # --- NUEVA RESPUESTA JSON ---
            return jsonify({
                "status": "success", 
                "message": f"Turno del {fecha_str} marcado como '{nuevo_reporte.estado}' correctamente.",
                "reporte_id": nuevo_reporte.id,
                "fecha_str": format_date_spanish(fecha_turno),
                "estado": nuevo_reporte.estado
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Error al procesar el turno: {e}"}), 500
        
    @app.route('/grupos/pdf')
    def pdf_grupos():
        """Genera y devuelve un PDF con todos los grupos activos."""
        # Usamos la misma lógica que en gestionar_grupos para obtener los grupos activos
        all_grupos = Grupo.query.all()
        grupos_activos = []
        hoy = datetime.date.today()
        for grupo in all_grupos:
            if grupo.fecha_fin >= hoy:
                grupos_activos.append(grupo)
            else:
                all_dates = set()
                current_date = grupo.fecha_inicio
                while current_date <= grupo.fecha_fin:
                    if current_date.weekday() < 5: all_dates.add(current_date)
                    current_date += datetime.timedelta(days=1)
                reportes_existentes = Reporte.query.filter_by(id_grupo=grupo.id).all()
                registered_dates = {r.fecha_turno for r in reportes_existentes}
                unregistered_dates = all_dates - registered_dates
                if unregistered_dates: grupos_activos.append(grupo)

        buf = generar_pdf_grupos(grupos_activos, "Reporte General de Grupos")
        return send_file(buf, as_attachment=True, download_name='reporte_grupos_general.pdf', mimetype='application/pdf')

    @app.route('/grupo/<int:id>/ver')
    def ver_grupo(id):
        """Muestra una página con los detalles de un solo grupo."""
        grupo = Grupo.query.get_or_404(id)
        return render_template('grupos/ver_grupo.html', grupo=grupo)

    @app.route('/grupo/<int:id>/pdf')
    def pdf_grupo(id):
        """Genera y devuelve un PDF para un grupo específico."""
        grupo = Grupo.query.get_or_404(id)
        buf = generar_pdf_grupos([grupo], f"Reporte del Grupo: {grupo.lugar}")
        return send_file(buf, as_attachment=True, download_name=f'reporte_grupo_{grupo.id}.pdf', mimetype='application/pdf')

# --- Bloque de ejecución directa (Opcional) ---
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5005, threaded=True, debug=True)
