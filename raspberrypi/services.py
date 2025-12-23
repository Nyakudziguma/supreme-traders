# econet/services.py
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import uuid
from django.conf import settings

class EcoCashService:
    def __init__(self):
        self.originator = settings.ECO_ORIGINATOR
        self.destination = settings.ECO_DESTINATION
        self.username = settings.ECO_USERNAME
        self.password = settings.ECO_PASSWORD
        self.api_url = settings.ECO_API_URL
    
    def create_transfer_payload(self, transaction):
        """Create API payload for EcoCash transfer"""
        message_reference = str(uuid.uuid4())
        message_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if transaction.transaction_type == "Agent":
            message_text = f"Agent:{transaction.ecocash_number}, amount: {transaction.amount}"
        else:
            name = transaction.ecocash_name or ""
            message_text = f"ecocash_number:{transaction.ecocash_number}, amount:{transaction.amount}, name:{name}"
        
        return {
            "originator": self.originator,
            "destination": self.destination,
            "messageText": message_text,
            "messageReference": message_reference,
            "messageDate": message_date,
            "messageValidity": "",
            "sendDateTime": ""
        }, message_reference
    
    def send_transaction(self, transaction):
        """Send transaction to EcoCash API"""
        payload, message_reference = self.create_transfer_payload(transaction)
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                auth=HTTPBasicAuth(self.username, self.password),
                timeout=30
            )
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response.json() if response.status_code == 200 else {'error': response.text},
                'message_reference': message_reference
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"API request failed: {str(e)}"
            }