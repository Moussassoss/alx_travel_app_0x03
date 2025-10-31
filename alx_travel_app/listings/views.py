import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Payment
from listings.tasks import send_booking_email

@api_view(['POST'])
def initiate_payment(request):
    """
    Initiates a Chapa payment for a booking and creates a Payment record in the DB.
    """
    data = request.data
    booking_reference = data.get('booking_reference')
    amount = data.get('amount')
    customer_email = data.get('email')

    if not booking_reference or not amount or not customer_email:
        return Response({"error": "Missing required fields"}, status=400)

    # Create payment record in DB
    payment = Payment.objects.create(
        booking_reference=booking_reference,
        amount=amount,
        status='Pending'
    )

    # Initiate Chapa payment
    payload = {
        "amount": amount,
        "currency": "ETB",  # change if needed
        "email": customer_email,
        "tx_ref": booking_reference,
        "callback_url": "https://your-domain.com/api/verify-payment/"
    }

    headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
    response = requests.post(f"{settings.CHAPA_BASE_URL}/initialize", json=payload, headers=headers)

    if response.status_code == 200 and 'data' in response.json():
        payment.transaction_id = response.json()['data']['id']
        payment.save()
        return Response({"payment_link": response.json()['data']['checkout_url']})
    
    return Response({"error": "Payment initiation failed"}, status=400)


@api_view(['GET'])
def verify_payment(request):
    """
    Verifies a payment using Chapa API and updates the Payment record.
    Sends a booking confirmation email asynchronously via Celery if payment succeeds.
    """
    tx_ref = request.GET.get('tx_ref')
    if not tx_ref:
        return Response({"error": "Missing tx_ref parameter"}, status=400)

    try:
        payment = Payment.objects.get(booking_reference=tx_ref)
    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)

    headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
    response = requests.get(f"{settings.CHAPA_BASE_URL}/verify/{payment.transaction_id}", headers=headers)

    if response.status_code == 200 and 'data' in response.json():
        status = response.json()['data']['status']

        if status == 'success':
            payment.status = 'Completed'
            payment.save()

            # Trigger email asynchronously via Celery
            customer_email = response.json()['data'].get('customer', {}).get('email') or payment.booking_reference
            booking_details = f"Payment of {payment.amount} for booking {payment.booking_reference} completed successfully."
            send_booking_email.delay(customer_email, booking_details)

        else:
            payment.status = 'Failed'
            payment.save()

        return Response({"status": payment.status})

    return Response({"error": "Verification failed"}, status=400)
