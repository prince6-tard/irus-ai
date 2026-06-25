import time
import random

def send_whatsapp(phone: str, message: str) -> bool:
    """
    Simulates sending a WhatsApp message.
    In a real implementation, this would connect to the Meta WhatsApp Cloud API or Twilio.
    """
    if not phone:
        return False
        
    print(f"--- SIMULATED WHATSAPP SEND ---")
    print(f"To: {phone}")
    print(f"Message preview: {message[:100]}...")
    print(f"-------------------------------")
    
    # Simulate network delay
    time.sleep(random.uniform(0.5, 1.5))
    
    # For simulation, we always succeed if there's a phone number
    return True
