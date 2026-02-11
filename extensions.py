# -*- coding: utf-8 -*-
"""
Este archivo centraliza las extensiones de Flask para evitar importaciones circulares.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Inicializamos las extensiones sin una aplicación específica.
# Se conectarán a la app más tarde en create_app().
db = SQLAlchemy()
migrate = Migrate()