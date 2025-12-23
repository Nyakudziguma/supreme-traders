from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import json
import os
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from rest_framework.permissions import AllowAny
from accounts.models import User
from pathlib import Path
from .handlers import MessageHandler
from .models import InitiateOrders, WhatsAppSession, EcocashPop, InitiateSellOrders
import hashlib
import hmac
import base64
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from signals.models import Subscribers

class WebhookView(APIView): 
    permission_classes = [AllowAny]
    def post(self, request):
        print(">>>>>>>>>>>>>>> Incoming data <<<<<<<<<<<<<<<<<<")
        data = json.loads(request.body)
        print(f"{data}")
        if 'object' in data and 'entry' in data:
            app_id = "3743370545965323"
            if data['object'] == 'whatsapp_business_account':
                try:
                    for entry in data['entry']:
                        entry_id = entry.get('id')
                        if entry_id == app_id:
                            fromId = entry['changes'][0]['value']['messages'][0]['from']
                            phoneId = entry['changes'][0]['value']['metadata']['phone_number_id']
                            profileName = entry['changes'][0]['value']['contacts'][0]['profile']['name']

                            if 'text' in entry['changes'][0]['value']['messages'][0]:
                                text = entry['changes'][0]['value']['messages'][0]['text']['body']
                            else:
                                text = None
                            if 'button' in entry['changes'][0]['value']['messages'][0]:
                                button = entry['changes'][0]['value']['messages'][0]['button']['payload']
                            else:
                                button = None
                            if 'image' in entry['changes'][0]['value']['messages'][0]:
                                image_id = entry['changes'][0]['value']['messages'][0]['image']['id']

                            else:
                                image_id = None
                            if 'document' in entry['changes'][0]['value']['messages'][0]:
                                document_id = entry['changes'][0]['value']['messages'][0]['document']['id']

                            else:
                                document_id = None

                            message = entry['changes'][0]['value']['messages'][0]
                            reply_data = None
                            selected_id = None
                            if 'interactive' in message:

                                if message['interactive']['type'] == 'button_reply':
                                    selected_id = message['interactive']['button_reply']['id']

                                
                                elif message['interactive']['type'] == 'list_reply':  
                                    selected_id = message['interactive']['list_reply']['id']
                                
                                elif message['interactive']['type'] == 'nfm_reply':
                                    interactive_data = message['interactive']
                                    reply_data = json.loads(interactive_data['nfm_reply']['response_json'])
                                    flow_token = reply_data.get('flow_token') 
                            else:
                                selected_id = None
                                reply_data = None

                            payload = None
                            if 'button' in message:
                                payload = message['button'].get('payload')

                            image = f"https://graph.facebook.com/v22.0/{image_id}"
                            document = f"https://graph.facebook.com/v22.0/{document_id}"
                            handler = MessageHandler()
                            handler.handle_incoming_message(fromId, text, phoneId, selected_id, reply_data, payload)
                            # WhatsappChatHandling(fromId, message, profileName, phoneId, text, image, selected_id, data, document, button, reply_data, payload)

                except Exception as e:
                   print(e)
        
        return HttpResponse('success', status=200)
    
    def get(self, request, *args, **kwargs):
        verify_token='badecb419530e1c3ee6f46bde4e66bb2e4867a4fa3ae1634bb14fee7269588a7a4bba9d358803356b89ae8f997e256100c2223d7598c74e91893d61a1a17596b'
        form_data = request.query_params
        mode = form_data.get('hub.mode')
        token = form_data.get('hub.verify_token')
        challenge = form_data.get('hub.challenge')
        print(f"{challenge}")
        return HttpResponse(challenge, status=200)


PRIVATE_KEY_PATH = Path("/root/supreme-traders/secure_keys/credspace_cba.pem")

with open(PRIVATE_KEY_PATH, "r") as key_file:
    PRIVATE_KEY = key_file.read()

@csrf_exempt
def create_deposit_order(request):
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
        elif request.content_type == 'application/x-www-form-urlencoded':
            body = request.POST.dict()
        else:
            return JsonResponse({'error': 'Unsupported content type'}, status=400)

        

        required_fields = ['encrypted_flow_data', 'encrypted_aes_key', 'initial_vector']
        for field in required_fields:
            if field not in body:
                raise ValueError(f"Missing required field: {field}")

        encrypted_flow_data_b64 = body['encrypted_flow_data']
        encrypted_aes_key_b64 = body['encrypted_aes_key']
        initial_vector_b64 = body['initial_vector']
        

        decrypted_data, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64)
        print(decrypted_data)
        
        if decrypted_data.get("version") == "3.0" and decrypted_data.get("action") == "ping":
            response = {
               "version": "3.0",
                "data": {
                    "status": "active"
                }
            }
            return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

        
        trader = User.objects.get(phone_number=decrypted_data.get("flow_token"))

        InitiateOrders.objects.filter(trader=trader).delete()

        try:
            InitiateOrders.objects.create(
                trader=trader,
                amount=decrypted_data['data'].get('amount'),
                account_number=decrypted_data['data'].get('account_number'),
                ecocash_number=decrypted_data['data'].get('ecocash_number')
            )
        except Exception as e:
            print(e)

        chat = WhatsAppSession.objects.get(user__phone_number=decrypted_data.get("flow_token"))
        chat.current_step = 'waiting_for_ecocash_pop'
        chat.previous_step = 'order_creation'
        chat.save()
        
        response = {
                "version": "3.0",
                "screen": "SUCCESS",
                "data": {
                    "extension_message_response": {
                        "params": {
                            "flow_token": decrypted_data.get("flow_token"),
                            "flow_state": "finish_flow_application",
                           
                        }
                    }
                }
            }

        return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

    except ValueError as ve:
        print(f'Oops, ValueError: {ve}')
        return JsonResponse({'error': str(ve)}, status=400)
    except json.JSONDecodeError as jde:
        print(f'Oops, JSONDecodeError: {jde}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f'Oops, Exception: {e}')
        return JsonResponse({'error': 'An error occurred while processing the request.'}, status=500)

import re

def normalize_account_number(account_number: str) -> str:
    """
    Ensures account number is in CR123456 format
    """
    if not account_number:
        raise ValueError("Account number is required")

    # Remove spaces and make uppercase
    acc = str(account_number).replace(" ", "").upper()

    # Extract digits
    digits = re.sub(r"\D", "", acc)

    if not digits:
        raise ValueError("Invalid account number format")

    return f"CR{digits}"


@csrf_exempt
def create_withdrawal_order(request):
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
        elif request.content_type == 'application/x-www-form-urlencoded':
            body = request.POST.dict()
        else:
            return JsonResponse({'error': 'Unsupported content type'}, status=400)

        

        required_fields = ['encrypted_flow_data', 'encrypted_aes_key', 'initial_vector']
        for field in required_fields:
            if field not in body:
                raise ValueError(f"Missing required field: {field}")

        encrypted_flow_data_b64 = body['encrypted_flow_data']
        encrypted_aes_key_b64 = body['encrypted_aes_key']
        initial_vector_b64 = body['initial_vector']
        

        decrypted_data, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64)
        print(decrypted_data)
        
        if decrypted_data.get("version") == "3.0" and decrypted_data.get("action") == "ping":
            response = {
               "version": "3.0",
                "data": {
                    "status": "active"
                }
            }
            return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

        
        trader = User.objects.get(phone_number=decrypted_data.get("flow_token"))
        account_number=decrypted_data['data'].get('account_number')

        InitiateSellOrders.objects.filter(account_number=account_number).delete()

        normalized_account = normalize_account_number(account_number)

        try:
            InitiateSellOrders.objects.create(
                trader=trader,
                amount=decrypted_data['data'].get('amount'),
                account_number=normalized_account,
                ecocash_number=decrypted_data['data'].get('ecocash_number'),
                ecocash_name=decrypted_data['data'].get('ecocash_name'),
                email=decrypted_data['data'].get('email')
            )
        except Exception as e:
            print(e)

        chat = WhatsAppSession.objects.get(user__phone_number=decrypted_data.get("flow_token"))
        chat.current_step = 'start_withdrawal_order'
        chat.previous_step = 'menu'
        chat.save()
        
        response = {
                "version": "3.0",
                "screen": "SUCCESS",
                "data": {
                    "extension_message_response": {
                        "params": {
                            "flow_token": decrypted_data.get("flow_token"),
                            "flow_state": "finish_flow_application",
                           
                        }
                    }
                }
            }

        return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

    except ValueError as ve:
        print(f'Oops, ValueError: {ve}')
        return JsonResponse({'error': str(ve)}, status=400)
    except json.JSONDecodeError as jde:
        print(f'Oops, JSONDecodeError: {jde}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f'Oops, Exception: {e}')
        return JsonResponse({'error': 'An error occurred while processing the request.'}, status=500)

@csrf_exempt
def add_ecocash_pop(request):
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
        elif request.content_type == 'application/x-www-form-urlencoded':
            body = request.POST.dict()
        else:
            return JsonResponse({'error': 'Unsupported content type'}, status=400)

        

        required_fields = ['encrypted_flow_data', 'encrypted_aes_key', 'initial_vector']
        for field in required_fields:
            if field not in body:
                raise ValueError(f"Missing required field: {field}")

        encrypted_flow_data_b64 = body['encrypted_flow_data']
        encrypted_aes_key_b64 = body['encrypted_aes_key']
        initial_vector_b64 = body['initial_vector']
        

        decrypted_data, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64)
        
        if decrypted_data.get("version") == "3.0" and decrypted_data.get("action") == "ping":
            response = {
               "version": "3.0",
                "data": {
                    "status": "active"
                }
            }
            return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

        
        trader = User.objects.get(phone_number=decrypted_data.get("flow_token"))
        print("Decrypted data for Ecocash POP:", decrypted_data)
           
        ecocash_pop_encryption_key = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('encryption_key')
        ecocash_pop_hmac_key = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('hmac_key')
        ecocash_pop_iv = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('iv')
        ecocash_pop_plaintext = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('plaintext_hash')
        ecocash_pop_encrypted_hash = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('encrypted_hash')
        ecocash_pop_cdn_url = decrypted_data['data'].get('ecocash_pop', [])[0].get('cdn_url')


        base_filename = f"{decrypted_data['data'].get('flow_token')}"
        ecocash_pop_filename = f"{base_filename}_ecocash_pop.jpg"
        ecocash_pop = decrypt_whatsapp_media(ecocash_pop_cdn_url, ecocash_pop_encryption_key, ecocash_pop_hmac_key, ecocash_pop_iv, ecocash_pop_plaintext, ecocash_pop_encrypted_hash, ecocash_pop_filename)
        print("Decrypted Ecocash POP saved at:", ecocash_pop)
        order = InitiateOrders.objects.get(trader=trader)
        if order:
            try:
                EcocashPop.objects.create(
                    order=order,
                    ecocash_pop=ecocash_pop
                )
            except Exception as e:
                print(e)
        else:
            print("No order found for the trader." )
            

        chat = WhatsAppSession.objects.get(user__phone_number=decrypted_data.get("flow_token"))
        chat.current_step = 'finish_order_creation'
        chat.previous_step = 'order_creation'
        chat.save()
        
        response = {
                "version": "3.0",
                "screen": "SUCCESS",
                "data": {
                    "extension_message_response": {
                        "params": {
                            "flow_token": decrypted_data.get("flow_token"),
                            "flow_state": "finish_flow_application",
                           
                        }
                    }
                }
            }

        return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

    except ValueError as ve:
        print(f'Oops, ValueError: {ve}')
        return JsonResponse({'error': str(ve)}, status=400)
    except json.JSONDecodeError as jde:
        print(f'Oops, JSONDecodeError: {jde}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f'Oops, Exception: {e}')
        return JsonResponse({'error': 'An error occurred while processing the request.'}, status=500)

@csrf_exempt
def add_ecocash_message_pop(request):
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
        elif request.content_type == 'application/x-www-form-urlencoded':
            body = request.POST.dict()
        else:
            return JsonResponse({'error': 'Unsupported content type'}, status=400)

        

        required_fields = ['encrypted_flow_data', 'encrypted_aes_key', 'initial_vector']
        for field in required_fields:
            if field not in body:
                raise ValueError(f"Missing required field: {field}")

        encrypted_flow_data_b64 = body['encrypted_flow_data']
        encrypted_aes_key_b64 = body['encrypted_aes_key']
        initial_vector_b64 = body['initial_vector']
        

        decrypted_data, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64)
        
        if decrypted_data.get("version") == "3.0" and decrypted_data.get("action") == "ping":
            response = {
               "version": "3.0",
                "data": {
                    "status": "active"
                }
            }
            return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

        
        trader = User.objects.get(phone_number=decrypted_data.get("flow_token"))
        print("Decrypted data for Ecocash POP:", decrypted_data)
    
        order = InitiateOrders.objects.get(trader=trader)
        if order:
            old_pop = EcocashPop.objects.filter(order=order).first()
            if old_pop:
                old_pop.delete()
            try:
                EcocashPop.objects.create(
                    order=order,
                    ecocash_message=decrypted_data['data'].get('ecocash_message'),
                    has_image=False
                )
            except Exception as e:
                print("Error on saving EcocashPop: ", e)
        else:
            print("No order found for the trader." )
            

        chat = WhatsAppSession.objects.get(user__phone_number=decrypted_data.get("flow_token"))
        chat.current_step = 'finish_order_creation'
        chat.previous_step = 'order_creation'
        chat.save()
        
        response = {
                "version": "3.0",
                "screen": "SUCCESS",
                "data": {
                    "extension_message_response": {
                        "params": {
                            "flow_token": decrypted_data.get("flow_token"),
                            "flow_state": "finish_flow_application",
                           
                        }
                    }
                }
            }

        return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

    except ValueError as ve:
        print(f'Oops, ValueError: {ve}')
        return JsonResponse({'error': str(ve)}, status=400)
    except json.JSONDecodeError as jde:
        print(f'Oops, JSONDecodeError: {jde}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f'Oops, Exception: {e}')
        return JsonResponse({'error': 'An error occurred while processing the request.'}, status=500)

@csrf_exempt
def add_signals_pop(request):
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
        elif request.content_type == 'application/x-www-form-urlencoded':
            body = request.POST.dict()
        else:
            return JsonResponse({'error': 'Unsupported content type'}, status=400)

        

        required_fields = ['encrypted_flow_data', 'encrypted_aes_key', 'initial_vector']
        for field in required_fields:
            if field not in body:
                raise ValueError(f"Missing required field: {field}")

        encrypted_flow_data_b64 = body['encrypted_flow_data']
        encrypted_aes_key_b64 = body['encrypted_aes_key']
        initial_vector_b64 = body['initial_vector']
        

        decrypted_data, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64)
        
        if decrypted_data.get("version") == "3.0" and decrypted_data.get("action") == "ping":
            response = {
               "version": "3.0",
                "data": {
                    "status": "active"
                }
            }
            return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

        
        trader = User.objects.get(phone_number=decrypted_data.get("flow_token"))
        print("Decrypted data for Ecocash POP:", decrypted_data)
           
        ecocash_pop_encryption_key = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('encryption_key')
        ecocash_pop_hmac_key = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('hmac_key')
        ecocash_pop_iv = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('iv')
        ecocash_pop_plaintext = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('plaintext_hash')
        ecocash_pop_encrypted_hash = decrypted_data['data'].get('ecocash_pop', [])[0].get('encryption_metadata', {}).get('encrypted_hash')
        ecocash_pop_cdn_url = decrypted_data['data'].get('ecocash_pop', [])[0].get('cdn_url')


        base_filename = f"{decrypted_data['data'].get('flow_token')}"
        ecocash_pop_filename = f"{base_filename}_ecocash_pop.jpg"
        ecocash_pop = decrypt_whatsapp_media(ecocash_pop_cdn_url, ecocash_pop_encryption_key, ecocash_pop_hmac_key, ecocash_pop_iv, ecocash_pop_plaintext, ecocash_pop_encrypted_hash, ecocash_pop_filename)
        print("Decrypted Ecocash POP saved at:", ecocash_pop)
        sub = Subscribers.objects.get(trader=trader)
        
        if sub:
            try:
                sub.ecocash_number = decrypted_data['data'].get('ecocash_number')
                sub.pop_image = ecocash_pop
                sub.save()
            except Exception as e:
                print(e)
        else:
            print("No subscription found for the trader." )
            

        chat = WhatsAppSession.objects.get(user__phone_number=decrypted_data.get("flow_token"))
        chat.current_step = 'finish_signal_subscription'
        chat.previous_step = 'signal_subscription'
        chat.save()
        
        response = {
                "version": "3.0",
                "screen": "SUCCESS",
                "data": {
                    "extension_message_response": {
                        "params": {
                            "flow_token": decrypted_data.get("flow_token"),
                            "flow_state": "finish_flow_application",
                           
                        }
                    }
                }
            }

        return HttpResponse(encrypt_response(response, aes_key, iv), content_type='text/plain')

    except ValueError as ve:
        print(f'Oops, ValueError: {ve}')
        return JsonResponse({'error': str(ve)}, status=400)
    except json.JSONDecodeError as jde:
        print(f'Oops, JSONDecodeError: {jde}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f'Oops, Exception: {e}')
        return JsonResponse({'error': 'An error occurred while processing the request.'}, status=500)



def decrypt_request(encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64):
    flow_data = b64decode(encrypted_flow_data_b64)
    iv = b64decode(initial_vector_b64)

    # Decrypt the AES encryption key
    encrypted_aes_key = b64decode(encrypted_aes_key_b64)
    private_key = load_pem_private_key(
        PRIVATE_KEY.encode('utf-8'), password=b'credspace')
    aes_key = private_key.decrypt(encrypted_aes_key, OAEP(
        mgf=MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

    # Decrypt the Flow data
    encrypted_flow_data_body = flow_data[:-16]
    encrypted_flow_data_tag = flow_data[-16:]
    decryptor = Cipher(algorithms.AES(aes_key),
                       modes.GCM(iv, encrypted_flow_data_tag)).decryptor()
    decrypted_data_bytes = decryptor.update(
        encrypted_flow_data_body) + decryptor.finalize()
    decrypted_data = json.loads(decrypted_data_bytes.decode("utf-8"))
    return decrypted_data, aes_key, iv

def encrypt_response(response, aes_key, iv):
    # Flip the initialization vector
    flipped_iv = bytearray()
    for byte in iv:
        flipped_iv.append(byte ^ 0xFF)

    # Encrypt the response data
    encryptor = Cipher(algorithms.AES(aes_key),
                       modes.GCM(flipped_iv)).encryptor()
    return b64encode(
        encryptor.update(json.dumps(response).encode("utf-8")) +
        encryptor.finalize() +
        encryptor.tag
    ).decode("utf-8")

def decrypt_whatsapp_media(cdn_url, encryption_key_b64, hmac_key_b64, iv_b64, plaintext_hash_b64, encrypted_hash_b64, filename):
    encryption_key = base64.b64decode(encryption_key_b64)
    hmac_key = base64.b64decode(hmac_key_b64)
    iv = base64.b64decode(iv_b64)
    encrypted_hash = base64.b64decode(encrypted_hash_b64)  # Decode the Base64 encrypted hash
    plaintext_hash = base64.b64decode(plaintext_hash_b64)  # Decode the Base64 plaintext hash

    # Step 1: Download the encrypted file
    response = requests.get(cdn_url)
    cdn_file = response.content

    # Step 2: Verify SHA-256 hash of the encrypted file
    cdn_file_hash = hashlib.sha256(cdn_file).digest()  # Get the hash in binary format

    if cdn_file_hash != encrypted_hash:
        raise ValueError("Encrypted file hash does not match.")
    else:
        print('Hash matched -----------------')

    # Step 3: Validate HMAC
    hmac10 = cdn_file[-10:]       # Last 10 bytes of cdn_file
    ciphertext = cdn_file[:-10]   # Ciphertext without HMAC bytes

    # Calculate HMAC-SHA256 and verify the first 10 bytes
    calculated_hmac = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()[:10]
    if calculated_hmac != hmac10:
        raise ValueError("HMAC validation failed.")

    # Step 4: Decrypt the media content using AES-256 CBC
    cipher = Cipher(algorithms.AES(encryption_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    decrypted_media = unpadder.update(padded_plaintext) + unpadder.finalize()

    # Step 5: Validate decrypted media
    decrypted_media_hash = hashlib.sha256(decrypted_media).digest()  # Get the hash in binary format
    if decrypted_media_hash != plaintext_hash:
        raise ValueError("Decrypted media hash does not match plaintext hash.")
    
    return  save_image_to_model(decrypted_media, filename)

def save_image_to_model(decrypted_media, filename):
    file_path = os.path.join('pop', filename) 
    content_file = ContentFile(decrypted_media)
    saved_path = default_storage.save(file_path, content_file)
    return saved_path