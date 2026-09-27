from icalendar import Calendar, Event, vCalAddress, vText, Alarm
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from organization.email_service import queue_bulk_emails

def convert_to_ical(booking):
    ical_event = Event()
    summary = f"{booking.item} - {booking.team} - {booking.team_contact}"
    ical_event.add('summary', summary)

    # Wrap date and time fields into datetime objects
    start_datetime = datetime.combine(booking.start_date, booking.start_time)
    end_datetime = datetime.combine(booking.end_date, booking.end_time)

    ical_event.add('dtstart', start_datetime)
    ical_event.add('dtend', end_datetime)

    # Initialize description parts
    description_parts = []

    # Add team contact name
    if booking.team_contact:
        description_parts.append(f"Kontaktperson: {booking.team_contact}")

    # Add team contact phone number
    if hasattr(booking.team_contact, 'phone') and booking.team_contact.phone:
        description_parts.append(f"Telefon: {booking.team_contact.phone}")

    # Add quantity (for TeknikBooking)
    if hasattr(booking, 'quantity') and booking.quantity:
        description_parts.append(f"Antal: {booking.quantity}")

    # Add remarks
    if hasattr(booking, 'remarks') and booking.remarks:
        description_parts.append(f"Noter:\n{booking.remarks}")

    # Add internal remarks
    if hasattr(booking, 'remarks_internal') and booking.remarks_internal:
        description_parts.append(f"Interne noter:\n{booking.remarks_internal}")

    # Add assistance and delivery info (for TeknikBooking)
    if hasattr(booking, 'assistance_needed'):
        assistance_text = "Ja" if booking.assistance_needed else "Nej"
        description_parts.append(f"Bistand nødvendig: {assistance_text}")
    if hasattr(booking, 'delivery_needed'):
        delivery_text = "Ja" if booking.delivery_needed else "Nej"
        description_parts.append(f"Levering nødvendig: {delivery_text}")

    # Add location (for AktivitetsTeamBooking with address and coordinates)
    if hasattr(booking, 'address') and hasattr(booking, 'location') and booking.location and booking.address:
        location_text = f"{booking.location}, {booking.address}"
        ical_event['location'] = vText(location_text)
        description_parts.append(f"Placering: {location_text}")

    # Add Google Maps URL (for AktivitetsTeamBooking with latitude/longitude fields)
    if hasattr(booking, 'latitude') and hasattr(booking, 'longitude') and booking.latitude and booking.longitude:
        prefix = "https://www.google.com/maps?q="
        separator = ","
        latitude = str(booking.latitude).replace('\\', '').strip()
        longitude = str(booking.longitude).replace('\\', '').strip()
        google_maps_url = prefix + latitude + separator + longitude
        description_parts.append(f"Link til location: {google_maps_url}")

    # Add location from LocationField (for TeknikBooking)
    if hasattr(booking, 'location') and booking.location and not hasattr(booking, 'address'):
        try:
            coords = str(booking.location).split(',')
            latitude = coords[0].strip()
            longitude = coords[1].strip()
            google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
            description_parts.append(f"Link til location: {google_maps_url}")
            ical_event['location'] = vText(f"Teknik ({latitude}, {longitude})")
        except (ValueError, IndexError):
            pass

    # Join all parts into the final description
    description_with_contact = "\n\n".join(description_parts)
    ical_event.add('description', description_with_contact)

    # Add attendees if assigned_aktivitetsteam exists (for AktivitetsTeamBooking)
    if hasattr(booking, 'assigned_aktivitetsteam') and booking.assigned_aktivitetsteam.exists():
        for volunteer in booking.assigned_aktivitetsteam.all():
            attendee = vCalAddress(f'MAILTO:{volunteer.email}')
            attendee.params['cn'] = vText(f"{volunteer.first_name} {volunteer.last_name}")
            attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
            ical_event.add('attendee', attendee, encode=0)

    # Add alarm
    alarm_1h_before = Alarm()
    alarm_1h_before.add('action', 'DISPLAY')
    alarm_1h_before.add('trigger', timedelta(hours=-1))
    alarm_1h_before.add('description', f"{booking.item} starter om 1 time")
    ical_event.add_component(alarm_1h_before)

    return ical_event

def export_selected_to_ical(queryset):
    calendar = Calendar()

    for booking in queryset:
        ical_event = convert_to_ical(booking)
        calendar.add_component(ical_event)

    return calendar.to_ical()

def send_ical_via_email(queryset, email_template, from_email):
    messages = []
    for booking in queryset:
        calendar = Calendar()
        ical_event = convert_to_ical(booking)
        calendar.add_component(ical_event)
        ical_content = calendar.to_ical()

        for volunteer in booking.assigned_aktivitetsteam.all():
            subject = f"Booking Detaljer for {booking.item}"
            context = {'volunteer': volunteer, 'booking': booking}
            message = render_to_string(email_template, context)
            plain_message = strip_tags(message)

            messages.append(
                {
                    "recipient": volunteer.email,
                    "subject": subject,
                    "body": plain_message,
                    "html_body": message,
                    "from_email": from_email,
                    "attachments": [
                        {
                            "filename": f"booking_{booking.id}.ics",
                            "content": ical_content,
                            "mimetype": "text/calendar",
                        }
                    ],
                }
            )
    return queue_bulk_emails(messages)
