import datetime
from extensions import db

# Tabla de asociación para la relación muchos-a-muchos entre Estudiantes y Grupos
estudiante_grupo = db.Table('estudiante_grupo',
    db.Column('id_estudiante', db.Integer, db.ForeignKey('estudiante.id'), primary_key=True),
    db.Column('id_grupo', db.Integer, db.ForeignKey('grupo.id'), primary_key=True)
)

class Ciclo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    estudiantes = db.relationship('Estudiante', backref='ciclo', lazy=True, cascade="all, delete-orphan")
    grupos = db.relationship('Grupo', backref='ciclo', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Ciclo {self.nombre}>'

class Estudiante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    carnet = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    semestre = db.Column(db.String(20), nullable=False)
    seccion = db.Column(db.String(10), nullable=False)
    estado_academico = db.Column(db.String(50), nullable=False, default='Pendiente de evaluación')
    fecha_pago = db.Column(db.Date, nullable=True)
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)

    def __repr__(self):
        return f'<Estudiante {self.carnet}>'

class Supervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(120), nullable=True)
    grupos = db.relationship('Grupo', backref='supervisor', lazy=True)

    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    def __repr__(self):
        return f'<Supervisor {self.nombre_completo()}>'

class Grupo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lugar = db.Column(db.String(200), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    modalidad = db.Column(db.String(10), nullable=False) # 'matutino' o 'vespertino'
    id_supervisor = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)
    tipo_pago = db.Column(db.String(20), nullable=False, default='20_turnos')
    estudiantes = db.relationship('Estudiante', secondary=estudiante_grupo, lazy='subquery',
        backref=db.backref('grupos', lazy=True))
    reportes = db.relationship('Reporte', backref='grupo', lazy=True, cascade="all, delete-orphan")

    def calcular_pago_total(self):
        if self.tipo_pago == '40_turnos':
            tarifa_por_estudiante = 800.0
        else: # Por defecto o si es '20_turnos'
            tarifa_por_estudiante = 400.0
        
        # Aplica la lógica del máximo de 10 estudiantes para el cálculo
        num_estudiantes_para_pago = min(len(self.estudiantes), 10)
        
        return num_estudiantes_para_pago * tarifa_por_estudiante

    def calcular_dias_habiles(self):
        # Cuenta los días de lunes a viernes entre las fechas
        dias_habiles = 0
        current_date = self.fecha_inicio
        while current_date <= self.fecha_fin:
            if current_date.weekday() < 5: # 0=Lunes, 4=Viernes
                dias_habiles += 1
            # CORRECCIÓN: Ahora usamos datetime.timedelta, que funcionará correctamente.
            current_date += datetime.timedelta(days=1)
        return dias_habiles if dias_habiles > 0 else 1 # Evitar división por cero

    def calcular_pago_por_turno(self):
        """
        Calcula el pago por turno para un grupo.
        - Considera un máximo de 10 estudiantes para el cálculo.
        - El pago por turno tiene un máximo de Q200.00.
        """
        pago_total = self.calcular_pago_total()
        # --- FIN DEL CAMBIO ---

        dias = self.calcular_dias_habiles()
        
        # Evitar división por cero
        if dias == 0:
            return 0.0
            
        # Calcula el pago base
        pago_sin_cap = pago_total / dias
        
        # El límite de Q200.00 por turno sigue aplicando
        pago_final = min(pago_sin_cap, 200.00)
        
        return round(pago_final, 2)

    def __repr__(self):
        return f'<Grupo {self.lugar} - {self.modalidad}>'

class Reporte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_grupo = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=False)
    id_supervisor = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    fecha_turno = db.Column(db.Date, nullable=False, default=datetime.date.today)
    estado = db.Column(db.String(20), default='realizado')
    pagado = db.Column(db.Boolean, default=False, nullable=False)
    pago_turno_fijado = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    supervisor = db.relationship('Supervisor', backref='reportes')

    def __repr__(self):
        return f'<Reporte {self.fecha_turno} - Grupo {self.id_grupo}>'