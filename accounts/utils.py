from .models import User
def create_user_from_whatsapp(phone_number, whatsapp_id, country=None):
    """Automatically create user when they message the WhatsApp bot"""
    
    # Check if user already exists
    user = User.objects.filter(phone_number=phone_number).first()
    if user:
        # Check if user is blocked
        if user.is_blocked:
            return None  # Or handle blocked user appropriately
        return user
    
    # Create new user
    user = User(
        phone_number=phone_number,
        whatsapp_id=whatsapp_id,
        registration_source='whatsapp',
        country=country,
        is_active=True
    )
    user.save()
    
    return user