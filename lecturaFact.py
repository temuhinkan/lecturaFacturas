import os
import re
import csv
import PyPDF2
import argparse

def extraer_datos_autodoc(lineas):
    """ Extracción específica para facturas Autodoc """
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,"AUTODOC SE",None, None, None,None

    for i, linea in enumerate(lineas):
        if re.search(r'Número de factura:', linea, re.IGNORECASE):
            numero_match = re.search(r'(\d{6,})', linea)
            if numero_match:
                numero_factura = numero_match.group(1)
        if re.search(r'NIF|CIF', linea, re.IGNORECASE): # Match based on "NIF" or "CIF" keywords
            print(f"Línea : {linea}")
            
            # Updated regex to handle multiple NIF/CIF formats
            cif_match = re.search(
                r'(?:NIF\s*\(número\s*de\s*identificación\s*fiscal\):\s*)' # Prefixes
                r'('                                                                                              # Start capturing group
                r'[A-Z]{2,3}[0-9]{7}[A-Z]'                                                                       # **NEW**: Pattern for ESN0040262H (ESN + 7 digits + 1 letter)
                r'|'                                                                                             # OR
                r'[A-Z]\d{8}'                                                                                    # Pattern for A87527800 (A + 8 digits)
                r'|\d{8}[A-Z]'                                                                                   # Pattern for XXXXXXXXA (8 digits + 1 letter, like DNI)
                r')', 
                linea, 
                re.IGNORECASE
            )
            
            print(f"cif_match : {cif_match}")
            if cif_match:
                cif = cif_match.group(1)
        if re.search(r'Fecha de factura:', linea, re.IGNORECASE):
            fecha_match = re.search(r'\d{2}[\./]\d{2}[\./]\d{4}', linea)
            if fecha_match:
                fecha = fecha_match.group(0)

        if 'Importe total bruto' in linea and i + 1 < len(lineas):
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', lineas[i+1])
            if valores:
                importe = valores[0]

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_stellantis(lineas):
    """ Extracción específica para facturas Stellantis """
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,"PPCR MADRID",None, None, None,None

    for i, linea in enumerate(lineas):
        if re.search(r'N° Factura', linea, re.IGNORECASE):
            numero_match = re.search(r'(\d{6,})', linea)
            if numero_match:
                numero_factura = numero_match.group(1)

        fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', linea)
        if fecha_match:
            fecha = fecha_match.group(1)

        if re.search(r'|NIF:', linea, re.IGNORECASE): # Match based on keywords
            # This regex ensures we capture an initial letter followed by exactly 8 digits.
            cif_match = re.search(r'(?:NIF:)\s*([A-Z]\d{8})', linea, re.IGNORECASE)
            if cif_match:
                cif = cif_match.group(1)
        if 'Total Factura' in linea:
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', linea)
            pos_total_factura = linea.find("Total Factura")
            importe_antes_total = None
            
            for valor in valores:
                if linea.find(valor) < pos_total_factura:
                    importe_antes_total = valor

            primer_valor = valores[0] if valores else None

            if primer_valor and importe_antes_total:
                primer_valor = float(primer_valor.replace(',', '.'))
                importe_antes_total = float(importe_antes_total.replace(',', '.'))
                importe = primer_valor + importe_antes_total

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_brildor(lineas):
   
    """ Extracción específica para facturas brildor """
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,"Brildor SL",None, None, None,None

    for i, linea in enumerate(lineas):
        if re.search(r'Factura', linea, re.IGNORECASE):
            numero_match = re.search(r'(\d{6,})', lineas[i+2])
            if numero_match:
                numero_factura = numero_match.group(1)
        if re.search(r'Fecha', linea, re.IGNORECASE):
            fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', lineas[i+1])
            if fecha_match:
                fecha = fecha_match.group(1)
        if re.search(r'Brildor SL', linea, re.IGNORECASE):
            cif_match = re.search(r'([A-Z]?\d{8}[A-Z]?)', linea)
            if cif_match:
                cif = cif_match.group(1)
        if 'Total' in linea:
            importe_match = re.search(r'(\d{1,3}(?:,\d{3})*(?:,\d{2}))', lineas[i+1])
            if importe_match:
                importe = importe_match.group(0)

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_hermanas(lineas):
    """ Extracción específica para facturas hermanas """
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,"Hermanas del Amor de Dios Casa General",None, None, None,None

    for i, linea in enumerate(lineas):
        if re.search(r'FACTURA', linea, re.IGNORECASE):
            numero_match = re.search(r'([A-Z]{2}-\d{2}/\d{4})', lineas[i+6])
            
            if numero_match:
                numero_factura = numero_match.group(1)
        if re.search(r'Fecha', linea, re.IGNORECASE):
            fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', linea)
            if fecha_match:
                fecha = fecha_match.group(1)
        if re.search(r'C.I.F', linea, re.IGNORECASE):
            print(f"Línea {i}: {linea}")
            cif_match = re.search(r'C\.?I\.?F\.?:?\s*([A-Z]?\d{7,8}[A-Z]?)', linea)
            if cif_match:
                cif = cif_match.group(1)
        if 'CONCEPTO IMPORTE' in linea:
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', linea)
            importe_match = valores[-1] if valores else None
            if importe_match:
                importe = importe_match

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_kiauto(lineas):
    """ Extracción específica para facturas kiauto"""
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,"AUTOLUX RECAMBIOS S.L",None, None, None,None

    for i, linea in enumerate(lineas):
       if re.search(r'factura', linea, re.IGNORECASE):
            numero_match = re.search(r'(\d{2}\.\d{3}\.\d{3})', lineas[i+1])
            if numero_match:
                numero_factura = numero_match.group(1)
       if re.search(r'Fecha factura', linea, re.IGNORECASE):
            fecha_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', lineas[i+1])
            if fecha_match:
                fecha = fecha_match.group(1)
       if re.search(r'AUTOLUX RECAMBIOS S.L', linea, re.IGNORECASE):
            cif_match = re.search(r'([A-Z]?\d{8}[A-Z]?)', linea)
            if cif_match:
                cif = cif_match.group(1)
       if  re.search(r'TOTAL FACTURA', linea, re.IGNORECASE):
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', lineas[i+2])
            
            importe_match = valores[-1] if valores else None
            if importe_match:
                importe = importe_match

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_sumauto(lineas):
    """ Extracción específica para facturas sumauto """
    tipo,fecha, numero_factura,cliente,cif,modelo,matricula, importe = "COMPRA", None, None,None,None, None, None,None

    for i, linea in enumerate(lineas):
        if re.search(r'FAC', linea, re.IGNORECASE):
            numero_match = re.search(r'([A-Z0-9_]+)', linea)
            if numero_match:
                numero_factura = numero_match.group(1)

        if re.search(r'Fecha de expedición', linea, re.IGNORECASE):
            fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', linea)
            if fecha_match:
                fecha = fecha_match.group(1)

        if re.search(r'TOTAL TARIFA', linea, re.IGNORECASE):
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', linea)
            importe_match = valores[-1] if valores else None
            if importe_match:
                importe = importe_match

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

def extraer_datos_generico(lineas):
    """ Extracción genérica para otros tipos de facturas """
    tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe = "COMPRA", None, None, None, None, None, None, None

    for i, linea in enumerate(lineas):
        if re.search(r'Fecha|Fecha de emisión', linea, re.IGNORECASE):
            fecha_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', linea)
            if fecha_match:
                fecha = fecha_match.group(1)

        if re.search(r'Nº Factura|Número de factura', linea, re.IGNORECASE):
            numero_match = re.search(r'([A-Z0-9_-]+)', linea)
            if numero_match:
                numero_factura = numero_match.group(1)

        if re.search(r'Cliente', linea, re.IGNORECASE):
            cliente_match = re.search(r'Cliente\s*:\s*(.*)', linea)
            if cliente_match:
                cliente = cliente_match.group(1).strip()

        if re.search(r'CIF|NIF|C.I.F', linea, re.IGNORECASE):
            cif_match = re.search(r'([A-Z]?\d{8}[A-Z]?)', linea)
            if cif_match:
                cif = cif_match.group(1)

        if re.search(r'Modelo', linea, re.IGNORECASE):
            modelo_match = re.search(r'Modelo\s*:\s*(.*)', linea)
            if modelo_match:
                modelo = modelo_match.group(1).strip()

        if re.search(r'Matrícula', linea, re.IGNORECASE):
            matricula_match = re.search(r'([A-Z0-9]{4,})', linea)
            if matricula_match:
                matricula = matricula_match.group(1)

        if re.search(r'Total Factura|Importe', linea, re.IGNORECASE):
            valores = re.findall(r'\d{1,3}(?:,\d{3})*(?:,\d{2})', linea)
            importe = valores[-1] if valores else None

    return tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe  # ✅ Siempre 8 valores

  

def extraer_datos(pdf_path, debug_mode=False):
    """ Detecta el tipo de factura y aplica la función correcta """
    print(f"✅ Entrando en extraer_datos() con archivo: {pdf_path} y debug_mode: {debug_mode}")
    
    with open(pdf_path, 'rb') as archivo:
        pdf = PyPDF2.PdfReader(archivo)
        texto = ''
        for pagina in pdf.pages:
            texto += pagina.extract_text() or ''
        lineas = texto.splitlines()

    if debug_mode:
        print("\n🔍 MODO DEBUG ACTIVADO: Mostrando todas las líneas del archivo\n")
        for i, linea in enumerate(lineas):
            print(f"Línea {i}: {linea}")

    nombre_archivo = os.path.basename(pdf_path).lower()

    if "autodoc" in nombre_archivo:
        return extraer_datos_autodoc(lineas)
    elif "stellantis" in nombre_archivo:
        return extraer_datos_stellantis(lineas)
    elif "brildor" in nombre_archivo:
        return extraer_datos_brildor(lineas)
    elif "hermanas" in nombre_archivo:
        return extraer_datos_hermanas(lineas)
    elif "kiauto" in nombre_archivo:
         return extraer_datos_kiauto(lineas)
    elif "sumauto" in nombre_archivo:
         return extraer_datos_sumauto(lineas)
    else:
        return extraer_datos_generico(lineas)

parser = argparse.ArgumentParser(description='Procesar un archivo PDF o todos los PDFs en una carpeta.')
parser.add_argument('ruta', help='Ruta a un archivo PDF o a una carpeta con archivos PDF')
parser.add_argument('--debug', action='store_true', help='Activar modo depuración (True/False)')
args = parser.parse_args()

ruta = args.ruta
debug_mode = args.debug
archivos_pdf = []

if os.path.isfile(ruta) and ruta.lower().endswith('.pdf'):
    archivos_pdf.append(ruta)
elif os.path.isdir(ruta):
    archivos_pdf = [os.path.join(ruta, archivo) for archivo in os.listdir(ruta) if archivo.lower().endswith('.pdf')]

if not archivos_pdf:
    print("❌ No se encontraron archivos PDF para procesar.")
    exit()

csv_path = os.path.join(os.path.dirname(ruta), 'facturas_resultado.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Archivo', 'Fecha', 'Número de Factura', 'Importe'])

    for archivo in archivos_pdf:
        print(f"📤 Llamando a extraer_datos() con archivo: {archivo} y debug_mode: {debug_mode}")
        tipo, fecha, numero_factura, cliente, cif, modelo, matricula, importe = extraer_datos(archivo, debug_mode)
        writer.writerow([
            os.path.basename(archivo),
            tipo or 'No encontrado',
            fecha or 'No encontrada',
            numero_factura or 'No encontrado',
            cliente or 'No encontrado',
            cif or 'No encontrado',
            modelo or 'No encontrado',
            matricula or 'No encontrado',
            (f"{float(str(importe).replace(',', '.')):.2f} €") if importe else 'No encontrado'
        ])

print(f"\n✅ ¡Hecho! Revisa: {csv_path}")
