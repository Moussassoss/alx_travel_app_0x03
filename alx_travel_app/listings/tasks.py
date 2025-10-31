from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_booking_email(user_email, booking_details):
    subject = 'Booking Confirmation'
    message = f"Dear user,\n\nYour booking has been confirmed:\n{booking_details}\n\nThank you!"
    email_from = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    send_mail(subject, message, email_from, recipient_list)
