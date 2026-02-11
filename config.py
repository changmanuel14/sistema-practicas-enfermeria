import os
from dotenv import load_dotenv
# Importamos quote_plus para manejar caracteres especiales en la contraseña
from urllib.parse import quote_plus
# Importamos las credenciales desde nuestro archivo
from conexion import Conhost, Conuser, Conpassword, Condb

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'una-clave-secreta-muy-dificil'

    # --- CAMBIO CLAVE: URI de conexión para MySQL con codificación segura ---
    # Usamos quote_plus() para evitar problemas con caracteres especiales
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{quote_plus(Conuser)}:{quote_plus(Conpassword)}@{Conhost}/{Condb}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
