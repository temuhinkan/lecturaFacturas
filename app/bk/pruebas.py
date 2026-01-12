import requests

url = "http://localhost:8090/v1/chat/completions"

# Ruta a la factura de Renault que subiste
ruta_imagen = r"C:\Users\temuh\OneDrive\Documentos\GitHub\lecturaFacturas\ultimasmandadas\WhatsApp Image 2025-12-30 at 19.07.17 (1).jpeg"

payload = {
    "model": "moondream2",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract the total amount and the date from this invoice. Return only JSON."},
                {"type": "image_url", "image_url": {"url": ruta_imagen}}
            ]
        }
    ]
}

response = requests.post(url, json=payload)

# Esto nos dirá qué está respondiendo el servidor exactamente
print("Código de estado:", response.status_code)
print("Respuesta completa del servidor:", response.text)

if 'choices' in response.json():
    print("Resultado:", response.json()['choices'][0]['message']['content'])
else:
    print("El servidor no devolvió resultados válidos.")