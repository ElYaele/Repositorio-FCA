"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Proyecto/__init__.py
Descripción: Inicialización del paquete raíz del proyecto Django.
Configuración: Inicialización del driver de conexión MySQL / MariaDB (PyMySQL).
====================================================================================================
Este archivo se ejecuta de manera preliminar durante el arranque del entorno Django.
Su función crítica es interceptar las llamadas al controlador nativo 'mysqlclient' (MySQLdb)
y enrutar las consultas a través de 'pymysql', permitiendo compatibilidad multiplataforma
(Windows, Linux, macOS y entornos Cloud/Docker) sin requerir compiladores de C++ o librerías
nativas del sistema operativo.
"""

import pymysql

# Instalar PyMySQL como sustituto binario de MySQLdb para compatibilidad con el backend de Django
pymysql.install_as_MySQLdb()
