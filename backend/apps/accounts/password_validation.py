import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class AsciiComplexityPasswordValidator:
    """Require a portable password with ASCII upper/lowercase letters and a digit."""

    message = _(
        'رمز عبور باید ۸ تا ۱۲۸ کاراکتر و شامل حداقل یک حرف بزرگ انگلیسی، '
        'یک حرف کوچک انگلیسی و یک عدد باشد. فاصله و حروف فارسی مجاز نیست.'
    )

    def validate(self, password, user=None):
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ValidationError(self.message, code='password_ascii_complexity')
        if not all(33 <= ord(char) <= 126 for char in password):
            raise ValidationError(self.message, code='password_ascii_complexity')
        if not re.search(r'[A-Z]', password):
            raise ValidationError(self.message, code='password_ascii_complexity')
        if not re.search(r'[a-z]', password):
            raise ValidationError(self.message, code='password_ascii_complexity')
        if not re.search(r'[0-9]', password):
            raise ValidationError(self.message, code='password_ascii_complexity')

    def get_help_text(self):
        return self.message
