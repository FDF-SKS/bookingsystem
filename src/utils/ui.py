"""Shared context mixins for the modular list and gallery templates.

The templates in ``templates/components`` are intentionally presentation-only.
These mixins keep the per-app view classes small: each view declares its labels
and URL names, and the shared template renders the same UI everywhere.
"""

from typing import Any


class BookingListContextMixin:
    """Context for ``components/booking_list.html``."""

    booking_list_title = "Bookinger"
    booking_list_create_url_name = ""
    booking_list_create_label = "Ny booking"
    booking_list_mobile_create_label = ""
    booking_list_kanban_url_name = ""
    booking_list_kanban_label = "Kanban"
    booking_list_approve_url_name = ""
    booking_list_reject_url_name = ""
    booking_list_update_url_name = ""
    booking_list_delete_url_name = ""
    booking_list_show_comments = True
    booking_list_show_quantity = True
    booking_list_show_team_contact = True
    booking_list_empty_message = "Du har ingen bookinger endnu."

    def get_booking_list_title(self) -> str:
        return self.booking_list_title

    def get_booking_list_subtitle(self) -> str:
        return ""

    def get_booking_list_deadline(self) -> str:
        return ""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "booking_list_title": self.get_booking_list_title(),
                "booking_list_subtitle": self.get_booking_list_subtitle(),
                "booking_list_deadline": self.get_booking_list_deadline(),
                "booking_list_create_url_name": self.booking_list_create_url_name,
                "booking_list_create_label": self.booking_list_create_label,
                "booking_list_mobile_create_label": self.booking_list_mobile_create_label,
                "booking_list_kanban_url_name": self.booking_list_kanban_url_name,
                "booking_list_kanban_label": self.booking_list_kanban_label,
                "booking_list_approve_url_name": self.booking_list_approve_url_name,
                "booking_list_reject_url_name": self.booking_list_reject_url_name,
                "booking_list_update_url_name": self.booking_list_update_url_name,
                "booking_list_delete_url_name": self.booking_list_delete_url_name,
                "booking_list_show_comments": self.booking_list_show_comments,
                "booking_list_show_quantity": self.booking_list_show_quantity,
                "booking_list_show_team_contact": self.booking_list_show_team_contact,
                "booking_list_empty_message": self.booking_list_empty_message,
            }
        )
        return context


class ItemListContextMixin:
    """Context for ``components/item_list_table.html`` (Depot-style table)."""

    item_list_title = "Katalog"
    item_list_subtitle = ""
    item_list_create_url_name = ""
    item_list_create_label = "Tilføj"
    item_list_create_icon = "bi-plus-circle"
    item_list_detail_url_name = ""
    item_list_update_url_name = ""
    item_list_delete_url_name = ""
    item_list_search_placeholder = "Søg efter navn, lokation, beskrivelse..."
    item_list_empty_title = "Ingen varer fundet"
    item_list_empty_message = "Der er endnu ingen varer i kataloget."
    item_list_icon = "bi-box-seam"
    item_list_show_location = True
    item_list_show_quantity = True
    item_list_show_description = True

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        items = context.get("object_list")
        if items is None:
            items = context.get("items", [])
        context.update(
            {
                "item_list_items": items,
                "item_list_title": self.item_list_title,
                "item_list_subtitle": self.item_list_subtitle,
                "item_list_create_url_name": self.item_list_create_url_name,
                "item_list_create_label": self.item_list_create_label,
                "item_list_create_icon": self.item_list_create_icon,
                "item_list_detail_url_name": self.item_list_detail_url_name,
                "item_list_update_url_name": self.item_list_update_url_name,
                "item_list_delete_url_name": self.item_list_delete_url_name,
                "item_list_search_placeholder": self.item_list_search_placeholder,
                "item_list_empty_title": self.item_list_empty_title,
                "item_list_empty_message": self.item_list_empty_message,
                "item_list_icon": self.item_list_icon,
                "item_list_show_location": self.item_list_show_location,
                "item_list_show_quantity": self.item_list_show_quantity,
                "item_list_show_description": self.item_list_show_description,
            }
        )
        return context


class ItemGalleryContextMixin:
    """Context for ``components/item_list_gallery.html`` (card gallery)."""

    item_list_title = "Katalog"
    item_list_subtitle = ""
    item_list_category_url_name = ""
    item_list_book_url_name = ""
    item_list_book_label = "Book mig!"
    item_list_book_icon = "bi-plus-circle"
    item_list_book_button_class = "btn-primary"
    item_list_show_detail = False
    item_list_detail_label = "Se mere"
    item_list_icon = "bi-box-seam"
    item_list_image_height = 200
    item_list_css_class = ""
    item_list_empty_icon = "bi-search"
    item_list_empty_title = "Ingen varer fundet"
    item_list_empty_message = "Prøv at nulstille filteret eller tjek tilbage senere."
    item_list_empty_reset_label = "Vis alle"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "item_list_title": self.item_list_title,
                "item_list_subtitle": self.item_list_subtitle,
                "item_list_category_url_name": self.item_list_category_url_name,
                "item_list_book_url_name": self.item_list_book_url_name,
                "item_list_book_label": self.item_list_book_label,
                "item_list_book_icon": self.item_list_book_icon,
                "item_list_book_button_class": self.item_list_book_button_class,
                "item_list_show_detail": self.item_list_show_detail,
                "item_list_detail_label": self.item_list_detail_label,
                "item_list_icon": self.item_list_icon,
                "item_list_image_height": self.item_list_image_height,
                "item_list_css_class": self.item_list_css_class,
                "item_list_empty_icon": self.item_list_empty_icon,
                "item_list_empty_title": self.item_list_empty_title,
                "item_list_empty_message": self.item_list_empty_message,
                "item_list_empty_reset_label": self.item_list_empty_reset_label,
            }
        )
        return context


class BookingDetailContextMixin:
    """Context for ``components/booking_detail.html``."""

    booking_detail_kicker = "Booking"
    booking_detail_list_url_name = ""
    booking_detail_list_label = "Bookinger"
    booking_detail_approve_url_name = ""
    booking_detail_reject_url_name = ""
    booking_detail_delete_url_name = ""
    booking_detail_show_comments = True
    booking_detail_show_history = True

    def get_booking_detail_kicker(self) -> str:
        return self.booking_detail_kicker

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "booking_detail_kicker": self.get_booking_detail_kicker(),
                "booking_detail_list_url_name": self.booking_detail_list_url_name,
                "booking_detail_list_label": self.booking_detail_list_label,
                "booking_detail_approve_url_name": self.booking_detail_approve_url_name,
                "booking_detail_reject_url_name": self.booking_detail_reject_url_name,
                "booking_detail_delete_url_name": self.booking_detail_delete_url_name,
                "booking_detail_show_comments": self.booking_detail_show_comments,
                "booking_detail_show_history": self.booking_detail_show_history,
            }
        )
        return context


class ItemDetailContextMixin:
    """Context for ``components/item_detail.html``."""

    item_detail_catalog_label = "Katalog"
    item_detail_list_url_name = ""
    item_detail_badge_label = "Vare nr."
    item_detail_icon = "bi-box-seam"
    item_detail_quantity_label = "Lagerbeholdning"
    item_detail_footer_text = ""
    item_detail_show_sidebar = False
    item_detail_show_created = True
    item_detail_show_last_updated = True

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "item_detail_catalog_label": self.item_detail_catalog_label,
                "item_detail_list_url_name": self.item_detail_list_url_name,
                "item_detail_badge_label": self.item_detail_badge_label,
                "item_detail_icon": self.item_detail_icon,
                "item_detail_quantity_label": self.item_detail_quantity_label,
                "item_detail_footer_text": self.item_detail_footer_text,
                "item_detail_show_sidebar": self.item_detail_show_sidebar,
                "item_detail_show_created": self.item_detail_show_created,
                "item_detail_show_last_updated": self.item_detail_show_last_updated,
            }
        )
        return context
