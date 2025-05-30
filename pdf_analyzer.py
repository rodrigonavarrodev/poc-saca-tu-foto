import os
import base64
import anthropic
from dotenv import load_dotenv
from PIL import Image
import io
import sys
import json
import re
import requests
import time

# Load environment variables
load_dotenv()

class InvoiceAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        # Obtener el directorio del proyecto de forma dinámica
        project_dir = os.path.dirname(os.path.abspath(__file__))
        self.companies_file = os.path.join(project_dir, "companies.json")
        self.api_key = os.getenv("TAPILA_API_KEY")
        self.login_api_key = os.getenv("TAPILA_LOGIN_API_KEY")
        self.client_username = os.getenv("TAPILA_CLIENT_USERNAME")
        self.client_password = os.getenv("TAPILA_CLIENT_PASSWORD")
        self.auth_token = None
        
    def get_auth_token(self):
        """Get authentication token from login service."""
        try:
            url = "https://login.prod.tapila.cloud/login"
            
            headers = {
                'x-api-key': self.login_api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                "clientUsername": self.client_username,
                "password": self.client_password
            }
            
            print("\nIntentando obtener token de autenticación...")
            response = requests.post(url, headers=headers, json=data)
            
            # Print response details for debugging
            print(f"Status code: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response body: {response.text}")
            
            response.raise_for_status()
            
            # Extract token from response
            token_data = response.json()
            
            # Check if we got a valid token
            if not token_data or 'accessToken' not in token_data:
                print("Error: La respuesta no contiene un token válido")
                print(f"Respuesta completa: {token_data}")
                raise ValueError("No se pudo obtener el token de autenticación")
                
            self.auth_token = token_data['accessToken']
            print("Token obtenido exitosamente")
            return self.auth_token
            
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener el token de autenticación: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error al decodificar la respuesta JSON: {str(e)}")
            return None
        except Exception as e:
            print(f"Error inesperado al obtener el token: {str(e)}")
            return None
            
    def normalize_company_name(self, name):
        """Normalize company name for comparison."""
        if not isinstance(name, str):
            return []
            
        # Convert to lowercase
        name = name.lower()
        
        # Split by slash and take each part
        name_parts = [part.strip() for part in name.split('/')]
        
        # Process each part
        normalized_parts = []
        for part in name_parts:
            # Remove common suffixes and legal forms
            part = re.sub(r'\b(s\.a\.|s\.a|sa|sociedad anonima|sociedad anónima)\b', '', part)
            # Remove special characters and extra spaces
            part = re.sub(r'[^\w\s]', '', part)
            part = re.sub(r'\s+', ' ', part)
            if part.strip():
                # Split into words and filter out common words
                words = part.strip().split()
                # List of common words to ignore
                common_words = {'y', 'de', 'la', 'el', 'los', 'las', 'del', 'para', 'por', 'con', 'en', 'a', 'o', 'u'}
                # Add only non-common words
                normalized_parts.extend([word for word in words if word not in common_words])
        
        return normalized_parts
        
    def image_to_base64(self, image_path):
        """Convert image to base64 string."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except PermissionError:
            print("\nError: No tienes permisos para leer el archivo.")
            print("Sugerencias:")
            print("1. Asegúrate de que el archivo no esté abierto en otro programa")
            print("2. Intenta mover el archivo a una carpeta donde tengas permisos (como el Escritorio)")
            print("3. Verifica que el archivo no esté bloqueado por el sistema")
            sys.exit(1)
        except FileNotFoundError:
            print("\nError: No se encontró el archivo.")
            print("Asegúrate de que la ruta sea correcta y el archivo exista.")
            sys.exit(1)
            
    def analyze_image(self, image_path, prompt):
        """Analyze an image using Claude's API."""
        try:
            # Convert image to base64
            image_base64 = self.image_to_base64(image_path)
            
            # Get file extension to determine media type
            _, ext = os.path.splitext(image_path)
            media_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }.get(ext.lower(), 'image/jpeg')
            
            # Create message with image content
            message = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
            
    def find_company_info(self, provider_name):
        """Find company information in the JSON file."""
        try:
            with open(self.companies_file, 'r') as f:
                companies_data = json.load(f)
            
            # Normalize provider name into words
            provider_words = self.normalize_company_name(provider_name)
            print(f"\nBuscando compañía con palabras: {', '.join(provider_words)}")
            
            # Palabras clave que son significativas para identificar una empresa
            significant_words = {'edenor', 'aysa', 'metrogas', 'telecom', 'personal', 'claro', 'movistar'}
            
            # Search for company in the services array
            matches = []
            for service in companies_data.get('services', []):
                if not isinstance(service, dict):
                    continue
                    
                # Get company name
                company_name = service.get('companyName', '')
                if not company_name:
                    continue
                
                # Normalize name and check for matches
                company_words = self.normalize_company_name(company_name)
                
                # Calculate match score
                matching_words = set(provider_words) & set(company_words)
                if matching_words:
                    # Calculate match score based on:
                    # 1. Number of matching words
                    # 2. Whether it's an exact match
                    # 3. Whether it contains significant words
                    # 4. Whether it's a partial match
                    exact_match = all(word in company_words for word in provider_words)
                    has_significant_word = any(word in significant_words for word in matching_words)
                    
                    # Calculate score with weights
                    score = (
                        len(matching_words) * 1.0 +  # Base score for matching words
                        (10.0 if exact_match else 0.0) +  # Bonus for exact match
                        (20.0 if has_significant_word else 0.0)  # Bonus for significant word
                    )
                    
                    match_score = {
                        'service': service,
                        'score': score,
                        'exact_match': exact_match,
                        'has_significant_word': has_significant_word,
                        'company_name': company_name,
                        'matching_words': matching_words
                    }
                    matches.append(match_score)
            
            if matches:
                # Sort matches by score
                matches.sort(key=lambda x: -x['score'])
                
                # Get the best match
                best_match = matches[0]
                print(f"\n  ✓ Mejor coincidencia encontrada: {best_match['company_name']}")
                print(f"  Palabras coincidentes: {', '.join(best_match['matching_words'])}")
                print(f"  Es coincidencia exacta: {'Sí' if best_match['exact_match'] else 'No'}")
                print(f"  Contiene palabra significativa: {'Sí' if best_match['has_significant_word'] else 'No'}")
                print(f"  Puntuación: {best_match['score']}")
                print(f"  Información de la compañía:")
                print(f"    - Código: {best_match['service'].get('companyCode', '')}")
                print(f"    - Tipo: {best_match['service'].get('companyType', '')}")
                print(f"    - Tags: {', '.join(best_match['service'].get('tags', []))}")
                print(f"    - Modalidades activas: {len([m for m in best_match['service'].get('modalities', []) if m.get('active', True)])}")
                
                return best_match['service']
            
            print("  ✗ No se encontraron coincidencias")
            return None
            
        except Exception as e:
            print(f"Error al leer el archivo de compañías: {str(e)}")
            return None
            
    def clean_identifier(self, identifier):
        """Limpia el identificador de espacios, puntos y guiones."""
        if not identifier:
            return ""
        return identifier.replace(" ", "").replace(".", "").replace("-", "")

    def extract_invoice_data(self, image_path, identifiers_to_find):
        """Extrae información general de la factura y los identificadores específicos."""
        try:
            # Leer la imagen
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Construir el prompt para Claude
            prompt = f"""Analiza esta imagen de factura y extrae la siguiente información en formato JSON:

1. Información general:
   - valor_factura: El monto total de la factura (número sin símbolos de moneda)
   - fecha_vencimiento: La fecha de vencimiento en formato YYYY-MM-DD
   - nombre_cliente: El nombre completo del cliente

2. Identificadores específicos:
   - {', '.join([f'{id["identifierName"]}: {id["description"]}' for id in identifiers_to_find])}

Formato de respuesta requerido:
{{
    "valor_factura": "1234.56",
    "fecha_vencimiento": "2024-03-15",
    "nombre_cliente": "Juan Pérez",
    "identificadores": {{
        "identificador1": "valor1",
        "identificador2": "valor2"
    }}
}}

IMPORTANTE:
- Los valores de los identificadores deben estar sin espacios, puntos ni guiones
- Si no encuentras algún identificador, devuelve una cadena vacía ("") para ese campo
- Si no encuentras la fecha de vencimiento, devuelve una cadena vacía ("")
- Si no encuentras el nombre del cliente, devuelve una cadena vacía ("")
- Si no encuentras el valor de la factura, devuelve "0.00"
"""

            # Hacer la consulta a Claude
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                system="Eres un asistente especializado en analizar facturas y extraer información específica.",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Procesar la respuesta
            try:
                # Intentar parsear la respuesta como JSON
                response_text = response.content[0].text
                # Limpiar la respuesta de posibles caracteres extra
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                data = json.loads(response_text)
                
                # Limpiar los identificadores
                if "identificadores" in data:
                    cleaned_identifiers = {}
                    for key, value in data["identificadores"].items():
                        cleaned_identifiers[key] = self.clean_identifier(value)
                    data["identificadores"] = cleaned_identifiers
                
                return data
            except json.JSONDecodeError as e:
                print(f"Error al parsear la respuesta JSON: {str(e)}")
                print(f"Respuesta recibida: {response_text}")
                # Si no se puede parsear como JSON, intentar extraer manualmente
                text = response_text
                data = {
                    "valor_factura": "0.00",
                    "fecha_vencimiento": "",
                    "nombre_cliente": "",
                    "identificadores": {}
                }
                
                # Extraer valor de la factura
                valor_match = re.search(r'valor_factura[":\s]+([\d,.]+)', text)
                if valor_match:
                    data["valor_factura"] = valor_match.group(1).replace(",", ".")
                
                # Extraer fecha de vencimiento
                fecha_match = re.search(r'fecha_vencimiento[":\s]+(\d{4}-\d{2}-\d{2})', text)
                if fecha_match:
                    data["fecha_vencimiento"] = fecha_match.group(1)
                
                # Extraer nombre del cliente
                nombre_match = re.search(r'nombre_cliente[":\s]+([^"\n]+)', text)
                if nombre_match:
                    data["nombre_cliente"] = nombre_match.group(1).strip()
                
                # Extraer identificadores
                for identifier in identifiers_to_find:
                    id_name = identifier["identifierName"]
                    id_match = re.search(f'{id_name}["\\s:]+([^"\\n]+)', text)
                    if id_match:
                        data["identificadores"][id_name] = self.clean_identifier(id_match.group(1).strip())
                    else:
                        data["identificadores"][id_name] = ""
                
                return data

        except Exception as e:
            print(f"Error al extraer datos de la factura: {str(e)}")
            return {
                "valor_factura": "0.00",
                "fecha_vencimiento": "",
                "nombre_cliente": "",
                "identificadores": {id["identifierName"]: "" for id in identifiers_to_find}
            }

    def consult_debt(self, company_code, modality_id, query_data):
        """Consult debt information using Tapila API."""
        try:
            # Get auth token if not already available
            if not self.auth_token:
                self.get_auth_token()
                if not self.auth_token:
                    return None
                    
            url = "https://services.prod.tapila.cloud/debts"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Accept-Encoding': 'deflate,gzip',
                'x-api-key': self.api_key,
                'x-authorization-token': self.auth_token
            }
            
            # Generate a unique external ID
            external_id = f"ext-{int(time.time())}"
            
            data = {
                "companyCode": company_code,
                "modalityId": modality_id,
                "queryData": query_data,
                "externalRequestId": external_id,
                "externalClientId": "pdf-analyzer"
            }
            
            # Print the curl command for debugging
            curl_command = f"""curl --location '{url}' \\
--header 'Content-Type: application/json' \\
--header 'Accept: application/json' \\
--header 'Accept-Encoding: deflate,gzip' \\
--header 'x-api-key: {self.api_key}' \\
--header 'x-authorization-token: {self.auth_token}' \\
--data '{json.dumps(data, indent=2)}'"""
            
            print("\nCurl command being used:")
            print(curl_command)
            print("\nMaking request...")
            
            response = requests.post(url, headers=headers, json=data)
            
            # Print response details
            print(f"\nResponse status code: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response body: {response.text}")
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error al consultar la deuda: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return None
            
    def analyze_invoice(self, image_path):
        """Analiza una factura y extrae la información necesaria."""
        try:
            # Analizar la factura para identificar la compañía y su categoría
            company_prompt = """Analiza esta factura y proporciona la siguiente información en formato JSON:

{
    "company_names": ["nombre1", "nombre2", ...],  // Lista de nombres comerciales de la compañía
    "category": "categoría del servicio",  // Ejemplo: "gas", "electricidad", "telecomunicaciones"
}

Instrucciones específicas:
1. Identifica todos los nombres comerciales posibles de la compañía
2. Si el nombre es compuesto (ej: "Camuzzi Pampeana"), incluye tanto el nombre completo como sus partes
3. Incluye abreviaturas y nombres alternativos
4. Identifica la categoría del servicio (gas, electricidad, telecomunicaciones, etc.)
5. Identifica el tipo de factura (residencial, comercial, industrial)
6. No incluyas direcciones, códigos postales u otra información"""

            # Obtener información de la factura
            invoice_info = self.analyze_image(image_path, company_prompt)
            try:
                invoice_data = json.loads(invoice_info)
                company_names = invoice_data.get("company_names", [])
                category = invoice_data.get("category", "").lower()
                invoice_type = invoice_data.get("invoice_type", "").lower()
            except json.JSONDecodeError:
                print("Error al procesar la respuesta de identificación de compañía")
                return None

            print(f"\nNombres de compañía detectados: {', '.join(company_names)}")
            print(f"Categoría detectada: {category}")
            print(f"Tipo de factura: {invoice_type}")

            # Buscar la compañía en el JSON
            company_info = None
            company_code = None
            
            # Intentar encontrar la compañía por nombre
            for company_name in company_names:
                temp_info = self.find_company_info(company_name)
                if temp_info:
                    # Encontramos una coincidencia, la seleccionamos sin verificar categoría
                    company_info = temp_info
                    company_code = temp_info.get("companyCode", "")
                    company_tags = [tag.lower() for tag in temp_info.get("tags", [])]
                    
                    print(f"\nCompañía seleccionada: {temp_info.get('companyName', '')}")
                    print(f"Código de compañía: {company_code}")
                    print(f"Tags de la compañía: {', '.join(company_tags)}")
                    print(f"Categoría detectada: {category}")
                    break  # Tomamos la primera coincidencia y terminamos

            if not company_info:
                print("\nNo se encontraron coincidencias para la compañía")
                return None

            # Ya tenemos la compañía, procedemos con sus modalidades
            print("\nBuscando modalidades activas...")
            modalities = company_info.get("modalities", [])
            
            # Filtrar modalidades activas
            active_modalities = []
            for modality in modalities:
                if isinstance(modality, dict) and modality.get("active", True):
                    active_modalities.append(modality)
            
            if not active_modalities:
                print("No hay modalidades activas para esta compañía")
                return None
            
            print(f"\nModalidades activas encontradas: {len(active_modalities)}")
            
            # Construir la lista de identificadores para buscar
            identifiers_to_find = []
            
            for i, modality in enumerate(active_modalities):
                print(f"\nModalidad {i+1}:")
                print(f"  ID: {modality.get('modalityId', 'N/A')}")
                print(f"  Título: {modality.get('modalityTitle', 'N/A')}")
                print(f"  Tipo: {modality.get('modalityType', 'N/A')}")
                
                # Obtener queryData, que puede ser una lista o un diccionario
                query_data = modality.get("queryData", [])
                
                # Procesar queryData si es una lista
                if isinstance(query_data, list):
                    for qd_item in query_data:
                        if isinstance(qd_item, dict):
                            description = qd_item.get("description", "")
                            identifier_name = qd_item.get("identifierName", "")
                            min_length = qd_item.get("minLength", "")
                            max_length = qd_item.get("maxLength", "")
                            data_type = qd_item.get("dataType", "")
                            help_text = qd_item.get("helpText", "")
                            
                            if description and identifier_name:
                                print(f"  Identificador: {identifier_name}")
                                print(f"  Descripción: {description}")
                                print(f"  Longitud mínima: {min_length}")
                                print(f"  Longitud máxima: {max_length}")
                                print(f"  Tipo de dato: {data_type}")
                                if help_text:
                                    print(f"  Ayuda: {help_text}")
                                
                                identifiers_to_find.append({
                                    "identifierName": identifier_name,
                                    "description": description,
                                    "min_length": min_length,
                                    "max_length": max_length,
                                    "dataType": data_type,
                                    "helpText": help_text,
                                    "modalityId": modality.get("modalityId", "")
                                })
                
                # Procesar queryData si es un diccionario
                elif isinstance(query_data, dict):
                    identifiers = query_data.get("identifiers", [])
                    if isinstance(identifiers, list):
                        for identifier in identifiers:
                            if isinstance(identifier, dict):
                                identifier_name = identifier.get("name", "")
                                identifier_description = identifier.get("description", "")
                                min_length = identifier.get("minLength", "")
                                max_length = identifier.get("maxLength", "")
                                data_type = identifier.get("dataType", "")
                                help_text = identifier.get("helpText", "")
                                
                                if identifier_name and identifier_description:
                                    print(f"  Identificador: {identifier_name}")
                                    print(f"  Descripción: {identifier_description}")
                                    print(f"  Longitud mínima: {min_length}")
                                    print(f"  Longitud máxima: {max_length}")
                                    print(f"  Tipo de dato: {data_type}")
                                    if help_text:
                                        print(f"  Ayuda: {help_text}")
                                    
                                    identifiers_to_find.append({
                                        "identifierName": identifier_name,
                                        "description": identifier_description,
                                        "min_length": min_length,
                                        "max_length": max_length,
                                        "dataType": data_type,
                                        "helpText": help_text,
                                        "modalityId": modality.get("modalityId", "")
                                    })
            
            if not identifiers_to_find:
                print("\nNo se encontraron identificadores para las modalidades")
                print("Usando modalidades completas para el análisis...")
                
                # Si no se encontraron identificadores, usamos las descripciones generales
                for i, modality in enumerate(active_modalities):
                    modality_id = modality.get("modalityId", "")
                    
                    # Determinar qué descripción usar para este tipo de modalidad
                    if modality.get("modalityType") == "barcode":
                        description = "Código de Barras"
                        identifier_name = "BARCODE"
                        min_length = ""
                        max_length = ""
                        data_type = "ALF"
                        help_text = "Código de barras ubicado en la factura"
                    else:
                        # Buscar alguna descripción en queryData
                        description = ""
                        identifier_name = ""
                        min_length = ""
                        max_length = ""
                        data_type = "ALF"
                        help_text = ""
                        
                        query_data = modality.get("queryData", [])
                        if isinstance(query_data, list) and len(query_data) > 0:
                            for item in query_data:
                                if isinstance(item, dict) and item.get("description"):
                                    description = item.get("description", "")
                                    identifier_name = item.get("identifierName", f"ID_{i}")
                                    min_length = item.get("minLength", "")
                                    max_length = item.get("maxLength", "")
                                    data_type = item.get("dataType", "ALF")
                                    help_text = item.get("helpText", "")
                                    break
                        
                        # Si aún no tenemos descripción, usar el título de la modalidad
                        if not description:
                            description = modality.get("modalityTitle", f"Modalidad {i+1}")
                            identifier_name = f"ID_{i}"
                    
                    print(f"  Usando identificador: {identifier_name}")
                    print(f"  Descripción: {description}")
                    print(f"  Longitud mínima: {min_length}")
                    print(f"  Longitud máxima: {max_length}")
                    print(f"  Tipo de dato: {data_type}")
                    if help_text:
                        print(f"  Ayuda: {help_text}")
                    
                    identifiers_to_find.append({
                        "identifierName": identifier_name,
                        "description": description,
                        "min_length": min_length,
                        "max_length": max_length,
                        "dataType": data_type,
                        "helpText": help_text,
                        "modalityId": modality_id
                    })
            
            print(f"\nIdentificadores a buscar: {len(identifiers_to_find)}")
            for id_item in identifiers_to_find:
                print(f"  - {id_item['identifierName']}: {id_item['description']}")
                if id_item['min_length'] or id_item['max_length'] or id_item['dataType']:
                    print(f"    Restricciones: {id_item['dataType'] or 'N/A'}, longitud: {id_item['min_length'] or 'N/A'}-{id_item['max_length'] or 'N/A'}")
                if id_item.get('helpText'):
                    print(f"    Ayuda: {id_item['helpText']}")
            
            # Construir el prompt específico para Claude
            descriptions_list = []
            for item in identifiers_to_find:
                descriptions_list.append(f'  "{item["description"]}": "valor"')
            
            json_template = ",\n".join(descriptions_list)
            
            # Construir la lista de descripciones con detalles adicionales para Claude
            detailed_descriptions = []
            for item in identifiers_to_find:
                desc = f"   - {item['description']}"
                
                # Añadir detalles sobre el tipo de dato y restricciones
                restrictions = []
                
                if item['dataType']:
                    data_type_desc = ""
                    if item['dataType'] == "NUM":
                        data_type_desc = "numérico (solo dígitos)"
                    elif item['dataType'] == "ALF":
                        data_type_desc = "alfanumérico"
                    elif item['dataType'] == "IMP":
                        data_type_desc = "importe/monto"
                    elif item['dataType'] == "CBA":
                        data_type_desc = "código de barras"
                    
                    if data_type_desc:
                        restrictions.append(f"tipo {data_type_desc}")
                
                length_desc = ""
                if item['min_length'] and item['max_length'] and item['min_length'] == item['max_length']:
                    length_desc = f"exactamente {item['min_length']} caracteres"
                else:
                    if item['min_length']:
                        length_desc = f"mínimo {item['min_length']} caracteres"
                    if item['max_length']:
                        if length_desc:
                            length_desc += f", máximo {item['max_length']} caracteres"
                        else:
                            length_desc = f"máximo {item['max_length']} caracteres"
                
                if length_desc:
                    restrictions.append(length_desc)
                
                if restrictions:
                    desc += f" ({', '.join(restrictions)})"
                
                # Añadir el texto de ayuda si existe
                if item.get('helpText'):
                    desc += f"\n     Ubicación: {item['helpText']}"
                
                detailed_descriptions.append(desc)
            
            identifiers_prompt = f"""Analiza esta factura y extrae la siguiente información:

1. Extrae los siguientes datos específicos con las restricciones indicadas:
{chr(10).join(detailed_descriptions)}

2. Información general de la factura:
   - Valor total de la factura
   - Fecha de vencimiento
   - Nombre del cliente o titular

Responde ÚNICAMENTE en este formato JSON simplificado:

{{
{json_template},
  "valor_factura": "monto",
  "fecha_vencimiento": "fecha",
  "nombre_cliente": "nombre"
}}

IMPORTANTE: 
- Los valores deben cumplir con las restricciones de tipo y longitud especificadas.
- Para identificadores numéricos (NUM), utiliza solo dígitos sin espacios, puntos ni guiones.
- Para identificadores alfanuméricos (ALF), elimina espacios, puntos y guiones.
- Para códigos de barras (CBA), extrae todos los dígitos sin espacios.
- Para importes/montos (IMP), usa formato de número con punto decimal.
- La respuesta debe ser SOLO el JSON, sin texto adicional antes o después."""

            # Obtener los datos de la factura usando Claude
            print("\nConsultando a Claude para extraer los identificadores...")
            identifiers_info = self.analyze_image(image_path, identifiers_prompt)
            
            try:
                # Limpiar la respuesta para asegurar que sea un JSON válido
                identifiers_info = identifiers_info.strip()
                if identifiers_info.startswith("```json"):
                    identifiers_info = identifiers_info[7:]
                if identifiers_info.endswith("```"):
                    identifiers_info = identifiers_info[:-3]
                identifiers_info = identifiers_info.strip()
                
                # Parsear el JSON
                claude_data = json.loads(identifiers_info)
                print("Respuesta JSON recibida de Claude")
                
                # Crear el diccionario de resultado
                invoice_data = {
                    "valor_factura": claude_data.get("valor_factura", "0.00"),
                    "fecha_vencimiento": claude_data.get("fecha_vencimiento", ""),
                    "nombre_cliente": claude_data.get("nombre_cliente", ""),
                    "identificadores": {}
                }
                
                # Mapear las descripciones a los identificadores internos
                for id_item in identifiers_to_find:
                    description = id_item["description"]
                    identifier_name = id_item["identifierName"]
                    # Buscar por descripción exacta
                    if description in claude_data:
                        value = claude_data[description]
                        clean_value = self.clean_identifier(value)
                        invoice_data["identificadores"][identifier_name] = clean_value
                        print(f"Encontrado {description}: {clean_value}")
                    else:
                        print(f"No se encontró valor para: {description}")
                
                print("Datos extraídos correctamente de la factura")
                
            except json.JSONDecodeError as e:
                print(f"Error al procesar el JSON de Claude: {str(e)}")
                print(f"Respuesta recibida: {identifiers_info}")
                try:
                    # Intentar procesar como texto plano si JSON falla
                    print("Intentando procesar como texto plano...")
                    lines = identifiers_info.strip().split('\n')
                    
                    # Crear diccionario para almacenar resultados
                    invoice_data = {
                        "valor_factura": "0.00",
                        "fecha_vencimiento": "",
                        "nombre_cliente": "",
                        "identificadores": {}
                    }
                    
                    # Procesar cada línea
                    for line in lines:
                        line = line.strip()
                        if not line or ":" not in line:
                            continue
                            
                        # Dividir en clave y valor
                        key, value = [part.strip() for part in line.split(":", 1)]
                        
                        # Verificar si es un campo general
                        if key.lower() in ["valor de la factura", "valor_factura", "monto"]:
                            value = re.sub(r'[^\d.,]', '', value)
                            invoice_data["valor_factura"] = value
                            print(f"Valor de factura: {value}")
                        elif key.lower() in ["fecha de vencimiento", "fecha_vencimiento"]:
                            invoice_data["fecha_vencimiento"] = value
                            print(f"Fecha de vencimiento: {value}")
                        elif key.lower() in ["nombre del cliente", "nombre_cliente"]:
                            invoice_data["nombre_cliente"] = value
                            print(f"Nombre del cliente: {value}")
                        else:
                            # Buscar coincidencias para los identificadores
                            for id_item in identifiers_to_find:
                                description = id_item["description"]
                                identifier_name = id_item["identifierName"]
                                
                                if key.lower() == description.lower():
                                    clean_value = self.clean_identifier(value)
                                    invoice_data["identificadores"][identifier_name] = clean_value
                                    print(f"Encontrado {description}: {clean_value}")
                                    break
                    
                    print("Datos extraídos mediante modo alternativo")
                    
                except Exception as e2:
                    print(f"Error en el procesamiento alternativo: {str(e2)}")
                    import traceback
                    print(traceback.format_exc())
                    return None
            except Exception as e:
                print(f"Error al procesar la respuesta de Claude: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return None
                
            # Asignar los identificadores a las modalidades
            for modality in active_modalities:
                modality_id = modality.get("modalityId", "")
                modality["identifiers"] = {}
                
                # Buscar los identificadores correspondientes a esta modalidad
                for id_item in identifiers_to_find:
                    if id_item["modalityId"] == modality_id:
                        identifier_name = id_item["identifierName"]
                        valor = invoice_data.get("identificadores", {}).get(identifier_name, "")
                        modality["identifiers"][identifier_name] = self.clean_identifier(valor)

            # Construir el resultado final con solo los campos solicitados
            simplified_modalities = []
            for modality in active_modalities:
                # Extraer las descripciones de queryData
                query_data_descriptions = []
                query_data = modality.get("queryData", [])
                if isinstance(query_data, list):
                    for qd_item in query_data:
                        if isinstance(qd_item, dict) and "description" in qd_item:
                            query_data_descriptions.append(qd_item["description"])
                
                # Extraer los identificadores encontrados
                identifiers_dict = modality.get("identifiers", {})
                
                # Crear la estructura simplificada de modalidad
                simplified_modality = {
                    "modalityId": modality.get("modalityId", ""),
                    "modalityType": modality.get("modalityType", ""),
                    "modalityTitle": modality.get("modalityTitle", ""),
                    "queryDataDescriptions": query_data_descriptions,
                    "identifiersEncontrados": identifiers_dict
                }
                
                simplified_modalities.append(simplified_modality)
            
            result = {
                "companyName": company_info.get("companyName", ""),
                "companyCode": company_code,
                "category": category,
                "modalities": simplified_modalities,
                "valor_factura": invoice_data.get("valor_factura", "0.00"),
                "fecha_vencimiento": invoice_data.get("fecha_vencimiento", ""),
                "nombre_cliente": invoice_data.get("nombre_cliente", "")
            }
            
            print("\nResultado del análisis:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            return result

        except Exception as e:
            print(f"Error al analizar la factura: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

def main():
    # Example usage
    analyzer = InvoiceAnalyzer()
    
    print("\nInstrucciones para usar el programa:")
    print("1. Prepara tu imagen de factura (formato JPG, PNG, GIF o WEBP)")
    print("2. Asegúrate de que la imagen no esté abierta en otro programa")
    print("3. Si la imagen está en la carpeta de Descargas, considera moverla al Escritorio")
    print("4. Cuando se te solicite, puedes:")
    print("   - Arrastrar la imagen a la terminal")
    print("   - O escribir manualmente la ruta (ejemplo: /Users/tu_usuario/Desktop/factura.jpg)")
    print("\n")
    
    # Analyze invoice
    image_path = input("Por favor, ingresa la ruta de la imagen de la factura: ").strip()
    
    # Remove any quotes that might be added when dragging and dropping
    image_path = image_path.strip('"\'')
    
    if os.path.exists(image_path):
        print("\nAnalizando la factura...")
        result = analyzer.analyze_invoice(image_path)
        if result:
            # Ya se imprime en analyze_invoice, no necesitamos imprimirlo aquí de nuevo
            # print("\nResultado del análisis:")
            # print(json.dumps(result, indent=2, ensure_ascii=False))
            pass
        else:
            print("\nNo se pudo analizar la factura.")
    else:
        print(f"\nError: No se encontró el archivo {image_path}")
        print("Por favor, verifica que la ruta sea correcta y el archivo exista.")

if __name__ == "__main__":
    main()
