#!/usr/bin/env python3
"""
Servidor backend para el Analizador de Facturas.
Este script proporciona solo las APIs necesarias sin la interfaz web.
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
from io import StringIO
import logging
from pdf_analyzer import InvoiceAnalyzer
import sys

# Configurar la aplicación Flask
app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas

# Asegurar que Python pueda encontrar los módulos en el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Clase para capturar logs
class LogCapture:
    def __init__(self):
        self.log_capture_string = StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture_string)
        self.log_handler.setLevel(logging.INFO)
        self.formatter = logging.Formatter('%(message)s')
        self.log_handler.setFormatter(self.formatter)
        self.logger = logging.getLogger()
        self.original_handlers = self.logger.handlers.copy()
        self.original_level = self.logger.level

    def start_capture(self):
        self.logger.handlers = [self.log_handler]
        self.logger.setLevel(logging.INFO)

    def stop_capture(self):
        self.logger.handlers = self.original_handlers
        self.logger.setLevel(self.original_level)

    def get_logs(self):
        log_contents = self.log_capture_string.getvalue()
        return log_contents.strip().split('\n') if log_contents else []

# Función para verificar si el tipo de archivo es permitido
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ruta para verificar el estado del servidor
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'Servidor funcionando correctamente'
    })

# Ruta para analizar facturas
@app.route('/analyze', methods=['POST'])
def analyze_invoice():
    # Verificar si se envió un archivo
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No se ha enviado ningún archivo',
            'logs': []
        }), 400

    file = request.files['file']

    # Verificar si el archivo tiene nombre
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'No se ha seleccionado ningún archivo',
            'logs': []
        }), 400

    # Verificar si el archivo es de un formato permitido
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': 'Formato de archivo no permitido. Use: PNG, JPG, JPEG, GIF o PDF',
            'logs': []
        }), 400

    try:
        # Guardar el archivo temporalmente
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, file.filename)
        file.save(temp_file_path)

        # Capturar logs durante el análisis
        log_capture = LogCapture()
        log_capture.start_capture()

        # Analizar la factura
        analyzer = InvoiceAnalyzer()
        result = analyzer.analyze_invoice(temp_file_path)

        # Detener la captura de logs
        log_capture.stop_capture()
        logs = log_capture.get_logs()

        # Eliminar el archivo temporal
        try:
            os.remove(temp_file_path)
        except Exception as e:
            logs.append(f"Error al eliminar archivo temporal: {str(e)}")

        # Si no se pudo extraer datos, devolver un error
        if not result or not isinstance(result, dict):
            return jsonify({
                'success': False,
                'error': 'No se pudieron extraer datos de la factura',
                'logs': logs
            }), 400

        return jsonify({
            'success': True,
            'data': result,
            'logs': logs
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [f"Error en el servidor: {str(e)}", error_details]
        }), 500

# Ruta para consultar deudas
@app.route('/query-debt', methods=['POST'])
def query_debt():
    try:
        # Obtener datos de la solicitud
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos para la consulta',
                'logs': ['Error: No se recibieron datos para la consulta']
            }), 400
        
        # Obtener los parámetros necesarios
        company_code = data.get('companyCode')
        modality_id = data.get('modalityId')
        query_data = data.get('queryData')
        
        # Validar parámetros
        validation_errors = []
        if not company_code:
            validation_errors.append("Falta el parámetro 'companyCode'")
        if not modality_id:
            validation_errors.append("Falta el parámetro 'modalityId'")
        if not query_data:
            validation_errors.append("Falta el parámetro 'queryData'")
            
        if validation_errors:
            return jsonify({
                'success': False,
                'error': 'Parámetros inválidos',
                'logs': validation_errors
            }), 400

        # Aquí iría la lógica de consulta de deuda
        # Por ahora devolvemos un mensaje de ejemplo
        return jsonify({
            'success': True,
            'message': 'Consulta de deuda recibida correctamente',
            'data': {
                'companyCode': company_code,
                'modalityId': modality_id,
                'queryData': query_data
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [f"Error en el servidor: {str(e)}"]
        }), 500

# Solo ejecutar el servidor si se ejecuta este archivo directamente
if __name__ == '__main__':
    # Obtener el puerto del entorno o usar 5001 por defecto
    port = int(os.environ.get('PORT', 5001))
    
    # Configurar el host basado en el entorno
    host = '0.0.0.0' if os.environ.get('ENVIRONMENT') == 'production' else '127.0.0.1'
    
    print("\n=====================================")
    print("  ANALIZADOR DE FACTURAS (BACKEND)")
    print("=====================================")
    print(f"\nServidor iniciado en: http://{host}:{port}")
    print(f"Para acceder desde otros dispositivos: http://<tu-ip>:{port}")
    print("\nPresiona Ctrl+C para detener el servidor")
    
    # Iniciar el servidor
    app.run(host=host, port=port, debug=False) 