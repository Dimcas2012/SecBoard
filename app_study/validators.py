import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

def validate_password_pci_dss(password):
    if len(password) < 8:
        raise ValidationError(_("Password must contain at least 8 characters."))
    if not re.search(r'\d', password):
        raise ValidationError(_("Password must contain at least one digit."))
    if not re.search(r'[A-Z]', password):
        raise ValidationError(_("Password must contain at least one uppercase letter."))
    if not re.search(r'[a-z]', password):
        raise ValidationError(_("Password must contain at least one lowercase letter."))