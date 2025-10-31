import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Payment

@api_view(['POST'])
def initiate_payment(request):
    data = request.data
    booking_reference = data.get('booking_reference')
    amount = data.get('amount')
    customer_email = data.get('email')

    # Create a payment record in DB
    payment = Payment.objects.create(
        booking_reference=booking_reference,
        amount=amount,
        status='Pending'
    )

    # Initiate Chapa payment
    payload = {
        "amount": amount,
        "currency": "ETB",  # or your currency
        "email": customer_email,
        "tx_ref": booking_reference,
        "callback_url": "https://your-domain.com/api/verify-payment/"
    }

    headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
    response = requests.post(f"{settings.CHAPA_BASE_URL}/initialize", json=payload, headers=headers)
    
    if response.status_code == 200:
        payment.transaction_id = response.json()['data']['id']
        payment.save()
        return Response({"payment_link": response.json()['data']['checkout_url']})
    return Response({"error": "Payment initiation failed"}, status=400)


@api_view(['GET'])
def verify_payment(request):
    tx_ref = request.GET.get('tx_ref')
    try:
        payment = Payment.objects.get(booking_reference=tx_ref)
    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)

    headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
    response = requests.get(f"{settings.CHAPA_BASE_URL}/verify/{payment.transaction_id}", headers=headers)
    
    if response.status_code == 200:
        status = response.json()['data']['status']
        if status == 'success':
            payment.status = 'Completed'
        else:
            payment.status = 'Failed'
        payment.save()
        return Response({"status": payment.status})
    return Response({"error": "Verification failed"}, status=400)
