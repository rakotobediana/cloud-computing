from flask import Flask, render_template, request, send_file, url_for, redirect
from azure.ai.translation.text import TextTranslationClient
from azure.storage.blob import BlobServiceClient
from io import BytesIO
import os
import requests
import uuid
from dotenv import load_dotenv

app = Flask(__name__)

# Charger le fichier .env
load_dotenv()

# Configuration Azure Blob Storage

BLOB_STORAGE_CREDENTIAL = os.getenv('BLOB_STORAGE_CREDENTIAL')
BLOB_ACCOUNT_URL= os.getenv('BLOB_ACCOUNT_URL')


BLOB_CONTAINER_NAME = "text-traduced"
blob_service_client = BlobServiceClient(account_url=BLOB_ACCOUNT_URL, credential=BLOB_STORAGE_CREDENTIAL)
container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

# Clé API et point de terminaison
key = os.getenv('key')
endpoint = "https://api.cognitive.microsofttranslator.com"
location = "francecentral"
constructed_url = f"{endpoint}/translate"

@app.route("/", methods=["GET", "POST"])
def index():
    translated_text = ""
    translated_file = None  # Variable pour le fichier traduit

    if request.method == "POST":
        # Vérifier si un fichier a été téléchargé
        if 'file' in request.files:
            uploaded_file = request.files['file']
            if uploaded_file.filename != '':
                # Lire le fichier téléchargé
                file_content = uploaded_file.read().decode('utf-8')

                # Paramètres de la requête pour la traduction
                target_language = request.form['language']
                params = {
                    'api-version': '3.0',
                    'to': [target_language]
                }

                headers = {
                    'Ocp-Apim-Subscription-Key': key,
                    'Ocp-Apim-Subscription-Region': location,
                    'Content-type': 'application/json',
                    'X-ClientTraceId': str(uuid.uuid4())
                }

                # Corps de la requête
                body = [{'text': file_content}]

                # Effectuer la requête à l'API de traduction
                response = requests.post(constructed_url, params=params, headers=headers, json=body)
                if response.status_code == 200:
                    response_data = response.json()
                    translated_text = response_data[0]['translations'][0]['text']

                    # Sauvegarder le texte traduit dans Azure Blob Storage
                    blob_client = container_client.get_blob_client("translated_file.txt")
                    blob_client.upload_blob(translated_text, overwrite=True)

                    # Créer un fichier à partir du texte traduit pour le téléchargement
                    translated_file = BytesIO(translated_text.encode('utf-8'))
                    translated_file.seek(0)
                else:
                    translated_text = "Erreur lors de la traduction."
        else:
            # Si aucun fichier n'est téléchargé, faire la traduction normale
            text_to_translate = request.form['text']
            target_language = request.form['language']
            params = {
                'api-version': '3.0',
                'to': [target_language]
            }

            headers = {
                'Ocp-Apim-Subscription-Key': key,
                'Ocp-Apim-Subscription-Region': location,
                'Content-type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4())
            }

            body = [{'text': text_to_translate}]
            response = requests.post(constructed_url, params=params, headers=headers, json=body)
            if response.status_code == 200:
                response_data = response.json()
                translated_text = response_data[0]['translations'][0]['text']
                # Sauvegarder dans Azure Blob Storage
                blob_client = container_client.get_blob_client("translated_text.txt")
                blob_client.upload_blob(translated_text, overwrite=True)
            else:
                translated_text = "Erreur lors de la traduction."

    return render_template("index.html", translated_text=translated_text, translated_file=translated_file)

@app.route("/download/<filename>")
def download(filename):
    # Télécharger le contenu du fichier depuis Azure Blob Storage
    blob_client = container_client.get_blob_client(filename)
    blob_data = blob_client.download_blob()
    file_content = blob_data.readall()

    # Créer un fichier à partir du contenu
    file_stream = BytesIO(file_content)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="text/plain"
    )

# Écouter sur le port spécifié par l'environnement
app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

