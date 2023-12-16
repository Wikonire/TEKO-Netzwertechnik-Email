import subprocess
import requests
import smtplib
import ssl
import email
import imaplib
from dotenv import load_dotenv
import os
import random
import time

load_dotenv()  # Lädt die Variablen aus der .env-Datei

# Voraussetzung: In einem Environment-File sind folgende Konstanten zu definieren:
#   OPENROUTESERVICE_API_KEY,
#   SMTP_SERVER,
#   SMTP_PORT_TLS oder SMTP_PORT_SSL,
#   ACCOUNT_EMAIL,
#   EMAIL_PASSWORD
#   API_ENDPOINT
#   MAILBOX

# Konfiguration
# Hier benötigst Du Deinen persönlichen API-Schlüssel für OpenRouteService.
# Du kannst einen Schlüssel erstellen, indem Du Dich auf https://openrouteservice.org/ registrierst.
OPENROUTESERVICE_API_KEY = os.environ.get('OPENROUTESERVICE_API_KEY')

# Gib hier den SMTP Server Deines Email-Anbieters ein. Für Google Mail wäre das beispielsweise 'smtp.gmail.com'.
SMTP_SERVER = os.environ.get('SMTP_SERVER')

# Der Port Deines SMTP-Servers für die Verbindung über TLS. Üblicherweise ist das der Port 587.
SMTP_PORT_TLS: int = int(os.environ.get('SMTP_PORT_TLS'))

# Der Port Deines SMTP-Servers für die Verbindung über SSL. Üblicherweise ist das der Port 465.
SMTP_PORT_SSL: int = int(os.environ.get('SMTP_PORT_SSL'))

# Trage hier die E-Mail-Adresse ein, über die Du Deine E-Mails versenden möchtest.
ACCOUNT_EMAIL = os.environ.get('ACCOUNT_EMAIL')

# Gib das Passwort für das oben genannte E-Mail-Konto ein. Stell sicher, dass es sicher ist!
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# Der IMAP-Server Deines E-Mail-Anbieters. Für Google Mail wäre das beispielsweise 'imap.gmail.com'.
IMAP_SERVER = os.environ.get('IMAP_SERVER')

# Der Name des Postfachs (Mailbox), in dem nach neuen E-Mails gesucht wird, üblicherweise "INBOX".
MAILBOX = os.environ.get('MAILBOX')

# Die URL-Endpunkte Deiner Mapping-API. Zum Beispiel "https://api.openrouteservice.org/geocode/search".
API_ENDPOINT = os.environ.get('API_ENDPOINT')

# Der Pfad zum GPG-Programm (exe) auf Deinem System, z.B. "/usr/bin/gpg" auf einem UNIX-ähnlichen System.
GPG_PATH = os.environ.get('GPG_PATH')

# Der Betreff der E-Mails, die gesendet und gelesen werden.
SUBJECT_EMAIL = os.environ.get('SUBJECT_EMAIL')

# Dies sollte ein gültiger GPG-Schlüssel sein, den Du mit einem GPG-Schlüssel-Management-Tool
# wie Kleopatra oder GNU Privacy Assistant erzeugen kannst.
GPG_KEY = os.environ.get('GPG_KEY')

# Hier benötigst Du einen Pfad zu einer temporären Datei, in der verschlüsselte Nachrichten gespeichert werden.
# Dies kann irgendein Pfad auf Deinem Dateisystem sein, z. B. "/tmp/encrypted_msg.gpg" auf UNIX-basierten Systemen.
TEMP_ENCRYPTED_PATH = os.environ.get('TEMP_ENCRYPTED_PATH')

# Dies ist der Pfad zu einer temporären Datei, in der entschlüsselte Nachrichten gespeichert werden.
# Es könnte irgendwo auf Deinem Dateisystem sein, z. B. "/tmp/decrypted_msg.txt".
TEMP_DECRYPTED_PATH = os.environ.get('TEMP_DECRYPTED_PATH')


def check_env_variables():
    # Define a list of required environment variables
    required_env_vars = [
        'OPENROUTESERVICE_API_KEY', 'SMTP_SERVER', 'SMTP_PORT_TLS',
        'SMTP_PORT_SSL', 'ACCOUNT_EMAIL', 'EMAIL_PASSWORD',
        'IMAP_SERVER', 'MAILBOX', 'API_ENDPOINT', 'GPG_PATH',
        'SUBJECT_EMAIL', 'GPG_KEY', 'TEMP_ENCRYPTED_PATH',
        'TEMP_DECRYPTED_PATH'
    ]

    # Check each variable and print a warning if it is not set
    for var in required_env_vars:
        if os.environ.get(var) is None:
            print(
                f'Warnung: Die Umgebungsvariable {var} '
                f'ist nicht gesetzt. Bitte stellen Sie sicher, dass sie in Ihre .env-Datei eingefügt ist.')


def generate_existing_address():
    existing_addresses = [
        "Wankdorffeldstrasse 102, 3014 Bern, Switzerland",  # TEKO Bern Adresse
        "Feldackerweg, 3065 Boll, Switzerland",  # Feldackerweg in Boll
        "Kramgasse 49, 3011 Bern, Switzerland",  # Zufällige Straße in Bern
        "Rathausgasse 10, 3000 Bern, Schweiz",  # Eine Adresse in Bern
        "Bundesplatz 3, 3005 Bern, Schweiz",  # Die Adresse des Bundeshauses in Bern
        "Bahnhofplatz 10A, 3011 Bern, Schweiz",  # Die Adresse des Bahnhofs Bern
        "Hodlerstrasse 8, 3011 Bern, Schweiz",  # Die Adresse des Kunstmuseums Bern
        "Monument im Fruchtland 3, 3006 Bern, Schweiz"  # Die Adresse des Zentrums Paul Klee
    ]
    return random.choice(existing_addresses)


# E-Mail Empfangen
def get_latest_new_email_with_subject(imap_server, account_email, password, mailbox, subject):
    try:
        with imaplib.IMAP4_SSL(imap_server) as server:
            server.login(account_email, password)
            server.select(mailbox)

            response, data = server.search(None, '(UNSEEN SUBJECT "{}")'.format(subject))

            # wenn es keine ungelesenen E-Mails mit dem angegebenen Betreff gibt
            if not data or not data[0]:
                return None

            # das letzte Element aufnehmen
            data = data[0].split()
            latest = data[-1]

            # die E-Mail als gelesen markieren
            server.store(latest, '+FLAGS', '\\Seen')

            # das E-Mail (RFC822) für die ID (latest) abrufen
            result, email_data = server.fetch(latest, "(BODY[])")
            raw_email = email_data[0][1].decode("utf-8")
            email_message = email.message_from_string(raw_email)

            # das 'From' Feld nehmen
            from_field = email_message['From']

            # den Email-body auslesen
            body = ""
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    break

            return from_field, body

    except imaplib.IMAP4.error as e:
        print(f"Eine IMAP-Fehler ist aufgetreten: {e}")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")


def login_to_server(server, account_email, password, mailbox):
    """
    Logs into the server with the given account email and password,
    and selects the mailbox to fetch emails from.
    """
    server.login(account_email, password)
    server.select(mailbox)


def get_latest_email_id(server):
    """
    Fetches the latest unseen email and marks it as read.
    """
    response, data = server.search(None, '(UNSEEN)')
    latest = data[0].split()[-1]
    server.store(latest, '+FLAGS', r'\Seen')
    return latest


def fetch_email_message(server, email_id):
    """
    Fetches the email message for the given email ID.
    """
    result, email_data = server.fetch(email_id, "(BODY[])")
    raw_email = email_data[0][1].decode("utf-8")
    email_message = email.message_from_string(raw_email)
    return email_message


def get_from_field(email_message):
    """
    Gets the 'From' field from the email message
    """
    return email_message['From']


def get_email_body(email_message):
    """
    Extracts the email body from the email message.
    """
    for part in email_message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True)


# E-Mail Senden
def send_mail(smtp_server, smtp_port, account_email, password, message, receiver_email):
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(account_email, password)
            server.sendmail(account_email, receiver_email, message)
    except smtplib.SMTPAuthenticationError:
        print("Fehler: Authentifizierungsfehler. Überprüfen Sie Benutzername und Passwort.")
    except smtplib.SMTPConnectError:
        print("Fehler: Verbindungsfehler. Überprüfen Sie Server und Port.")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")


# Verschlüssele die Nachricht
def encrypt_message(recipient_mail, message, gpg_path):
    # Save message to temporary file
    print(f"Verschlüsselt die Nachricht: {message}")
    temp_message_path = "./tmp.txt"
    with open(temp_message_path, "w") as temp_message:
        temp_message.writelines(message)

    # gpg --recipient <recipient_mail> --batch --encrypt <temp_message_path>
    status = subprocess.check_call([
        gpg_path,
        "--yes",
        "--batch",
        "--armor",
        "--recipient", recipient_mail,
        "--output", temp_message_path + ".asc",
        "--encrypt", temp_message_path
    ])

    # after encryption, read and delete the text file
    temp_message_path_encrypted = f"{temp_message_path}.asc"

    if status == 0:
        with open(temp_message_path_encrypted, mode='r') as file:
            encrypted_message = file.read()

        os.remove(temp_message_path)
        os.remove(temp_message_path_encrypted)

        return encrypted_message  # This is your encrypted message.


def decrypt_message(encrypted_message, gpg_path):
    """
    Decrypts data using key.
    """

    if isinstance(encrypted_message, str):
        encrypted_message = encrypted_message.encode()

    try:
        # Write the encrypted message to a temp file
        with open(TEMP_ENCRYPTED_PATH, "wb") as f:
            f.write(encrypted_message)

        # Decrypt the message
        process = subprocess.run([gpg_path, "--output", TEMP_DECRYPTED_PATH, "--decrypt", TEMP_ENCRYPTED_PATH])

        # Check the return code to make sure the decryption was successful
        if process.returncode != 0:
            raise ValueError(f"GPG decryption failed with return code: {process.returncode}")

        # Read the decrypted message
        with open(TEMP_DECRYPTED_PATH, "r") as f:
            decrypted_message = f.read()

        return decrypted_message

    finally:
        # Clean up temp files
        if os.path.exists(TEMP_ENCRYPTED_PATH):
            os.remove(TEMP_ENCRYPTED_PATH)
        if os.path.exists(TEMP_DECRYPTED_PATH):
            os.remove(TEMP_DECRYPTED_PATH)


# REST API Abfragen
def get_coordinates(api_endpoint, address):
    url = f"{api_endpoint}?api_key={OPENROUTESERVICE_API_KEY}&text={address}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["features"]:
            print(f"Die Koordinaten für die Adresse {address} ist {data["features"][0]["geometry"]["coordinates"]}")
            return data["features"][0]["geometry"]["coordinates"]
        else:
            print(f"Keine passenden Geolocation-Ergebnisse gefunden für Adresse {address}")
            return None
    else:
        print(f"Anfrage führte zu einem Fehler mit Statuscode {response.status_code}")


def prepare_message(text, subject):
    print(f"Bereitet die Message vor für Adresse {subject}")
    # Prepare the email
    from email.mime.text import MIMEText
    msg = MIMEText(text)
    msg['Subject'] = f"{SUBJECT_EMAIL} {subject}"
    msg['From'] = ACCOUNT_EMAIL
    msg['To'] = ACCOUNT_EMAIL
    return msg


from colorama import Fore, init

init()


def print_green(message):
    print(Fore.GREEN + message)
    print(Fore.RESET)  # Reset the console color


def main():
    try:
        check_env_variables()
        # Step 1: Generate an address
        address = generate_existing_address()

        # Step 2: Get coordinates for the address
        coordinates = get_coordinates(API_ENDPOINT, address)
        if coordinates is None:
            raise ValueError("Keine Koordinaten gefunden. Überprüfen Sie die API-Endpunkt-Einstellungen.")

        # Step 3: Encrypt the coordinates
        encrypted_message = encrypt_message(GPG_KEY, str(coordinates), GPG_PATH)

        # Step 4: Prepare the email message
        message = prepare_message(encrypted_message, address)

        # Step 5: Send the email
        send_mail(SMTP_SERVER, SMTP_PORT_SSL, ACCOUNT_EMAIL, EMAIL_PASSWORD,
                  message.as_string(), message['To'])
        print('E-Mail verschickt, warte 30 Sekunden...')
        time.sleep(30)

        # Step 6: Fetch the latest email
        print('Nach E-Mail suchen...')
        sender, encrypted_body = get_latest_new_email_with_subject(IMAP_SERVER, ACCOUNT_EMAIL,
                                                                   EMAIL_PASSWORD, MAILBOX,
                                                                   SUBJECT_EMAIL)

        # Check if an email was found
        if sender is None or encrypted_body is None:
            raise ValueError("Kein Absender oder keine verschlüsselte Nachricht gefunden. Überprüfen Sie die "
                             "E-Maileinstellungen.")

        # Step 7: Decrypt the message
        decrypted_message = decrypt_message(encrypted_body, GPG_PATH)
        print_green(f'Entschlüsselte Nachricht: {decrypted_message}')

        # Step 8: Encrypt the decrypted message again
        encrypted_message = encrypt_message(GPG_KEY, str(decrypted_message), GPG_PATH)

        # Step 9: Send back the encrypted message
        message = prepare_message(encrypted_message, 'Koordinaten')
        send_mail(SMTP_SERVER, SMTP_PORT_SSL, ACCOUNT_EMAIL, EMAIL_PASSWORD, message, sender)
        print('E-Mail mit verschlüsselten Nachricht gesendet.')

    except ValueError as e:
        print(f"Ein Wertfehler ist aufgetreten: {e}")
    except TypeError as e:
        print(f"Ein Typfehler ist aufgetreten: {e}")
    except Exception as e:
        print(f"Ein allgemeiner Fehler ist aufgetreten: {e}")


if __name__ == '__main__':
    main()
