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
    estudiantes = db.relationship('Estudiante', secondary=estudiante_grupo, lazy='subquery',
        backref=db.backref('grupos', lazy=True))
    reportes = db.relationship('Reporte', backref='grupo', lazy=True, cascade="all, delete-orphan")

    def calcular_pago_total(self):
        return len(self.estudiantes) * 400

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
        pago_total = self.calcular_pago_total()
        dias = self.calcular_dias_habiles()
        return round(pago_total / dias, 2)

    def __repr__(self):
        return f'<Grupo {self.lugar} - {self.modalidad}>'

class Reporte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_grupo = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=False)
    id_supervisor = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    fecha_turno = db.Column(db.Date, nullable=False, default=datetime.date.today)
    estado = db.Column(db.String(20), default='realizado') # 'realizado', 'ausente', 'justificado'
    pagado = db.Column(db.Boolean, default=False, nullable=False)
    supervisor = db.relationship('Supervisor', backref='reportes')

    def __repr__(self):
        return f'<Reporte {self.fecha_turno} - Grupo {self.id_grupo}>'