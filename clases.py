import firebase_admin
from firebase_admin import credentials, firestore

# ================= CONFIGURACIÓN DE FIREBASE =================
# Recuerda que debes tener tu archivo JSON de credenciales en la misma carpeta
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    # Evita errores si la app ya fue inicializada en otra parte del ciclo de ejecución
    pass

db = firestore.client()

# ================= GESTIÓN DE USUARIOS (CRUD) =================

def obtener_usuario(username):
    """Busca un usuario en la colección por su ID de documento."""
    doc_ref = db.collection("usuarios").document(username)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def crear_nuevo_usuario(username, datos_usuario):
    """Crea un nuevo usuario y le inicializa su documento de exámenes en blanco."""
    # 1. Guardar el perfil en la colección 'usuarios'
    db.collection("usuarios").document(username).set(datos_usuario)
    
    # 2. Inicializar el control de exámenes para evitar errores de 'No Asignado'
    db.collection("examenes").document(username).set({
        "teorico": "No Asignado",
        "practico": "No Asignado"
    })
    return True

def eliminar_usuario_completo(username):
    """Elimina permanentemente el usuario y sus registros vinculados de Cloud Firestore."""
    # 1. Borrar el perfil del usuario
    db.collection("usuarios").document(username).delete()
    
    # 2. Borrar su historial de exámenes para no dejar datos huérfanos
    db.collection("examenes").document(username).delete()
    
    # 3. Limpieza opcional: Borrar las clases agendadas de este estudiante
    clases_ref = db.collection("clases").where("estudiante_username", "==", username).stream()
    for clase_doc in clases_ref:
        db.collection("clases").document(clase_doc.id).delete()
        
    return True

# ================= GESTIÓN DE CLASES Y AGENDAMIENTO =================

def agendar_clase(estudiante_user, profesor_user, tipo_clase, fecha, hora, vehiculo=None):
    """Registra una nueva sesión de clase en la colección general."""
    nueva_clase = {
        "estudiante_username": estudiante_user,
        "profesor_username": profesor_user,
        "tipo": tipo_clase,  # 'teorica' o 'practica'
        "fecha": fecha,
        "hora": hora,
        "vehiculo": vehiculo if tipo_clase == "practica" else "",
        "completada": False
    }
    # Firebase genera un ID automático único para cada clase agendada
    db.collection("clases").add(nueva_clase)
    return True

def obtener_clases_estudiante(username):
    """Trae todas las clases agendadas para un estudiante en específico."""
    clases_ref = db.collection("clases").where("estudiante_username", "==", username).stream()
    lista_clases = []
    for doc in clases_ref:
        datos = doc.to_dict()
        datos['id'] = doc.id
        lista_clases.append(datos)
    return lista_clases

def obtener_clases_profesor(username):
    """Trae todas las clases asignadas a un profesor en específico."""
    clases_ref = db.collection("clases").where("profesor_username", "==", username).stream()
    lista_clases = []
    for doc in clases_ref:
        datos = doc.to_dict()
        datos['id'] = doc.id
        lista_clases.append(datos)
    return lista_clases

def marcar_asistencia(clase_id):
    """El profesor confirma que el alumno asistió a la clase."""
    db.collection("clases").document(clase_id).update({"completada": True})
    return True

# ================= REGLAS DE NEGOCIO Y PRERREQUISITOS =================

def tiene_todas_teoricas_completas(username):
    """Verifica si el alumno ya asistió a TODAS las clases teóricas que le fueron agendadas."""
    # 1. Contamos cuántas clases teóricas totales le creó la recepción
    clases_totales_ref = db.collection("clases")\
                           .where("estudiante_username", "==", username)\
                           .where("tipo", "==", "teorica").stream()
    totales = sum(1 for _ in clases_totales_ref)
    
    # Si la recepción ni siquiera le ha agendado ninguna clase, no puede presentar examen
    if totales == 0:
        return False
        
    # 2. Contamos a cuántas de esas clases ya asistió (completada == True)
    clases_asistidas_ref = db.collection("clases")\
                             .where("estudiante_username", "==", username)\
                             .where("tipo", "==", "teorica")\
                             .where("completada", "==", True).stream()
    asistidas = sum(1 for _ in clases_asistidas_ref)
    
    # El botón solo se libera si asistió a absolutamente todas las programadas
    return asistidas == totales


def tiene_todas_practicas_completas(username):
    """Verifica si el alumno ya asistió a TODAS las clases prácticas que le fueron agendadas."""
    # 1. Contamos cuántas clases prácticas totales le creó la recepción
    clases_totales_ref = db.collection("clases")\
                           .where("estudiante_username", "==", username)\
                           .where("tipo", "==", "practica").stream()
    totales = sum(1 for _ in clases_totales_ref)
    
    # Si no tiene clases prácticas agendadas, no hay examen práctico aún
    if totales == 0:
        return False
        
    # 2. Contamos cuántas prácticas ya están completadas por el profesor
    clases_asistidas_ref = db.collection("clases")\
                             .where("estudiante_username", "==", username)\
                             .where("tipo", "==", "practica")\
                             .where("completada", "==", True).stream()
    asistidas = sum(1 for _ in clases_asistidas_ref)
    
    return asistidas == totales
# ================= GESTIÓN DE EXÁMENES =================

def obtener_todos_los_examenes():
    """Trae la matriz completa de notas de exámenes para el control de la recepción y docentes."""
    examenes_ref = db.collection("examenes").stream()
    return {doc.id: doc.to_dict() for doc in examenes_ref}

def asignar_examen(username, tipo_examen):
    """La recepción autoriza y agenda el examen ('teorico' o 'practico') cambiando el estado a Asignado."""
    db.collection("examenes").document(username).update({
        tipo_examen: "Asignado"
    })
    return True

def evaluar_examen(username, tipo_examen, resultado):
    """El profesor califica el examen asignado como 'Aprobado' o 'Reprobado'."""
    db.collection("examenes").document(username).update({
        tipo_examen: resultado
    })
    return True