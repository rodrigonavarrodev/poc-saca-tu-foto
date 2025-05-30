# Analizador de Facturas - Backend

Este es el backend del Analizador de Facturas, que proporciona APIs para analizar facturas y consultar deudas.

## Requisitos

- Python 3.8 o superior
- Dependencias listadas en `requirements.txt`

## Instalación

1. Clona este repositorio
2. Instala las dependencias:
```bash
pip3 install -r requirements.txt
```

3. Crea un archivo `.env` con las siguientes variables:
```
ANTHROPIC_API_KEY=tu_api_key_de_anthropic
TAPILA_API_KEY=tu_api_key_de_tapila
TAPILA_LOGIN_API_KEY=tu_login_api_key_de_tapila
TAPILA_CLIENT_USERNAME=tu_usuario
TAPILA_CLIENT_PASSWORD=tu_contraseña
```

## Uso

1. Inicia el servidor:
```bash
python3 backend_server.py
```

2. El servidor estará disponible en:
   - Localmente: `http://localhost:5001`
   - Desde otros dispositivos: `http://<tu-ip>:5001`

## APIs Disponibles

### 1. Analizar Factura
- **Endpoint**: `/analyze`
- **Método**: POST
- **Formato**: multipart/form-data
- **Parámetros**:
  - `file`: Archivo de factura (PDF, PNG, JPG, JPEG, GIF)
- **Respuesta**:
  ```json
  {
    "success": true,
    "data": {
      "companyName": "Nombre de la empresa",
      "category": "Categoría",
      "nombre_cliente": "Nombre del cliente",
      "fecha_vencimiento": "Fecha",
      "valor_factura": "Valor",
      "identifiers": {
        // Identificadores encontrados
      }
    },
    "logs": []
  }
  ```

### 2. Consultar Deuda
- **Endpoint**: `/query-debt`
- **Método**: POST
- **Formato**: application/json
- **Parámetros**:
  ```json
  {
    "companyCode": "código_de_empresa",
    "modalityId": "id_de_modalidad",
    "queryData": {
      // Datos específicos para la consulta
    }
  }
  ```
- **Respuesta**:
  ```json
  {
    "success": true,
    "message": "Consulta de deuda recibida correctamente",
    "data": {
      "companyCode": "código_de_empresa",
      "modalityId": "id_de_modalidad",
      "queryData": {
        // Datos de la consulta
      }
    }
  }
  ```

## Estructura del Proyecto

- `backend_server.py`: Servidor Flask principal
- `pdf_analyzer.py`: Lógica de análisis de facturas y consulta de deudas
- `companies.json`: Base de datos de empresas y servicios
- `requirements.txt`: Dependencias del proyecto
- `.env`: Variables de entorno (no incluido en el repositorio)
