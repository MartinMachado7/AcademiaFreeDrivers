from flask import Flask, render_template, request, redirect, url_for, session
import clases

app = Flask(__name__)

# Clave secreta necesaria para encriptar las sesiones de los usuarios en el navegador
app.secret_key = 'mi_clave_secreta_super_segura_para_free_drivers'

@app.route('/')
def home():
    return render_template('inicio.html')

# ================= CONTROL DE ACCESO (LOGIN / LOGOUT) =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario_ingresado')
        clave = request.form.get('clave_ingresada')
        
        # Consulta real en la colección 'usuarios' de Firebase
        datos_user = clases.obtener_usuario(usuario)
        
        if datos_user and datos_user['clave'] == clave:
            # Guardamos el diccionario del usuario en la sesión única de este navegador
            session['usuario'] = datos_user
            return redirect(url_for('academia'))
            
        return "<h3>Error: Credenciales inválidas. <a href='/login'>Volver</a></h3>"
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Limpiamos los datos de sesión de este navegador en específico
    session.pop('usuario', None)
    return redirect(url_for('home'))

# ================= PANEL PRINCIPAL (DASHBOARD) =================

@app.route('/academia')
def academia():
    # Recuperamos el usuario de la sesión actual
    usuario_actual = session.get('usuario')
    
    if not usuario_actual:
        return redirect(url_for('login'))
        
    clases_estudiante = []
    clases_profesor = []
    todos_los_usuarios = {}
    
    # LÓGICA DE CONTROL SEGÚN EL ROL DE LA SESIÓN
    if usuario_actual['rol'] == 'recepcionista':
        # Traemos todos los usuarios desde Firebase para la nueva casilla de gestión
        usuarios_ref = clases.db.collection("usuarios").stream()
        todos_los_usuarios = {doc.id: doc.to_dict() for doc in usuarios_ref}
    
    elif usuario_actual['rol'] == 'estudiante':
        # 1. Traemos todas las clases agendadas de este alumno
        todas_sus_clases = clases.obtener_clases_estudiante(usuario_actual['username'])
        
        # 2. Consultamos su estado de exámenes actual en Firebase
        mis_examenes = clases.obtener_todos_los_examenes().get(usuario_actual['username'], {})
        estado_teorico = mis_examenes.get('teorico', 'No Asignado')
        
        # 3. Aplicamos la regla de negocio (Filtro de Prerrequisitos)
        clases_estudiante = []
        for c in todas_sus_clases:
            if c['tipo'] == 'teorica':
                # Las teóricas siempre las puede ver
                clases_estudiante.append(c)
            elif c['tipo'] == 'practica' and estado_teorico == 'Aprobado':
                # Las prácticas SOLO se muestran si ya aprobó el examen teórico
                clases_estudiante.append(c)
        
    elif usuario_actual['rol'] == 'profesor':
        clases_profesor = clases.obtener_clases_profesor(usuario_actual['username'])
        
    return render_template('academia.html', 
                           usuario=usuario_actual, 
                           clases_e=clases_estudiante, 
                           clases_p=clases_profesor,
                           examenes=clases.obtener_todos_los_examenes(),
                           todos_usuarios=todos_los_usuarios,
                           modulo_clases=clases)

# ================= ACCIONES DE LA RECEPCIÓN =================

@app.route('/academia/registrar', methods=['GET', 'POST'])
def registrar():
    usuario_actual = session.get('usuario')
    
    # Restricción de seguridad perimetral
    if not usuario_actual or usuario_actual['rol'] != 'recepcionista':
        return "Acceso denegado: Se requieren permisos de recepción.", 403
        
    if request.method == 'POST':
        username = request.form.get('nuevo_usuario')
        nuevo_user = {
            "nombre": request.form.get('nuevo_nombre'),
            "username": username,
            "rol": request.form.get('nuevo_rol'),
            "clave": request.form.get('nueva_clave')
        }
        # Guardar de forma estructurada en Firebase Cloud Firestore
        clases.crear_nuevo_usuario(username, nuevo_user)
        return "<h3>Usuario creado exitosamente en la nube. <a href='/academia'>Volver</a></h3>"
        
    return render_template('registrar.html')

@app.route('/academia/eliminar-usuario', methods=['POST'])
def eliminar_usuario():
    usuario_actual = session.get('usuario')
    
    if not usuario_actual or usuario_actual['rol'] != 'recepcionista':
        return "Acceso denegado: Operación no autorizada.", 403
        
    username_a_borrar = request.form.get('estudiante_username')
    
    # Regla de negocio defensiva: Evitar auto-eliminación
    if username_a_borrar == usuario_actual['username']:
        return "<h3>Error: No puedes eliminar tu propia cuenta de recepción. <a href='/academia'>Volver</a></h3>"
        
    # Ejecuta el borrado doble en Firebase (documento de usuario + documento de examen)
    clases.eliminar_usuario_completo(username_a_borrar)
    return redirect(url_for('academia'))

@app.route('/academia/crear-clase', methods=['POST'])
def crear_clase():
    usuario_actual = session.get('usuario')
    if not usuario_actual or usuario_actual['rol'] != 'recepcionista': 
        return "No autorizado", 403
        
    clases.agendar_clase(
        estudiante_user=request.form.get('estudiante'), 
        profesor_user=request.form.get('profesor'), 
        tipo_clase=request.form.get('tipo'), 
        fecha=request.form.get('fecha'), 
        hora=request.form.get('hora'), 
        vehiculo=request.form.get('vehiculo')
    )
    return redirect(url_for('academia'))

@app.route('/academia/asignar-examen', methods=['POST'])
def asignar_examen():
    usuario_actual = session.get('usuario')
    if not usuario_actual or usuario_actual['rol'] != 'recepcionista': 
        return "No autorizado", 403
        
    estudiante = request.form.get('estudiante_username')
    tipo = request.form.get('tipo_examen') # 'teorico' o 'practico'
    
    clases.asignar_examen(estudiante, tipo)
    return redirect(url_for('academia'))

# ================= ACCIONES DEL PROFESOR =================

@app.route('/academia/confirmar-asistencia', methods=['POST'])
def confirmar_asistencia():
    usuario_actual = session.get('usuario')
    if not usuario_actual or usuario_actual['rol'] != 'profesor': 
        return "No autorizado", 403
        
    clase_id = request.form.get('clase_id')
    clases.marcar_asistencia(clase_id)
    return redirect(url_for('academia'))

@app.route('/academia/evaluar-examen', methods=['POST'])
def evaluar_examen():
    usuario_actual = session.get('usuario')
    if not usuario_actual or usuario_actual['rol'] != 'profesor': 
        return "No autorizado", 403
        
    estudiante = request.form.get('estudiante_username')
    tipo = request.form.get('tipo_examen')
    resultado = request.form.get('resultado') # 'Aprobado' o 'Reprobado'
    
    clases.evaluar_examen(estudiante, tipo, resultado)
    return redirect(url_for('academia'))

# ================= ARRANQUE DEL SERVIDOR LOCAL =================

if __name__ == '__main__':
    app.run(debug=True)