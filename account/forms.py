from __future__ import unicode_literals

import re

try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = None

from django import forms
from django.utils.translation import ugettext_lazy as _

from django.contrib import auth
from django.contrib.auth import get_user_model

from account.conf import settings
from account.hooks import hookset
from account.models import EmailAddress
from account.utils import get_user_lookup_kwargs


alnum_re = re.compile(r"^\w+$")


class SignupForm(forms.Form):

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.TextInput(), required=True
    )


    username = forms.CharField(
        label=_("Username"),
        max_length=30,
        widget=forms.TextInput(),
        required=True
    )
    password = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput(render_value=False)
    )
    password_confirm = forms.CharField(
        label=_("Senha (novamente)"),
        widget=forms.PasswordInput(render_value=False)
    )

    code = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.HiddenInput()
    )

    def clean_username(self):
        if not alnum_re.search(self.cleaned_data["username"]):
            raise forms.ValidationError(_("Usernames can only contain letters, numbers and underscores."))
        User = get_user_model()
        lookup_kwargs = get_user_lookup_kwargs({
            "{username}__iexact": self.cleaned_data["username"]
        })
        qs = User.objects.filter(**lookup_kwargs)
        if not qs.exists():
            return self.cleaned_data["username"]
        raise forms.ValidationError(_("Este nome de usuário já está sendo utilizado. Por favor escolha um outro."))

    def clean_email(self):
        value = self.cleaned_data["email"]
        qs = EmailAddress.objects.filter(email__iexact=value)
        if not qs.exists() or not settings.ACCOUNT_EMAIL_UNIQUE:
            return value
        raise forms.ValidationError(_("Um usuário já está registrado com esse email."))

    def clean(self):
        if "password" in self.cleaned_data and "password_confirm" in self.cleaned_data:
            if self.cleaned_data["password"] != self.cleaned_data["password_confirm"]:
                raise forms.ValidationError(_("You must type the same password each time."))
        return self.cleaned_data


class LoginForm(forms.Form):

    password = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput(render_value=False)
    )
    remember = forms.BooleanField(
        label=_("Lembrar"),
        required=False
    )
    user = None

    def clean(self):
        if self._errors:
            return
        user = auth.authenticate(**self.user_credentials())
        if user:
            if user.is_active:
                self.user = user
            else:
                raise forms.ValidationError(_("This account is inactive."))
        else:
            raise forms.ValidationError(self.authentication_fail_message)
        return self.cleaned_data

    def user_credentials(self):
        return hookset.get_user_credentials(self, self.identifier_field)


class LoginUsernameForm(LoginForm):

    username = forms.CharField(label=_("Username"), max_length=30)
    authentication_fail_message = _("O usuário ou senha especificados não estão corretos.")
    identifier_field = "username"

    def __init__(self, *args, **kwargs):
        super(LoginUsernameForm, self).__init__(*args, **kwargs)
        field_order = ["username", "password", "remember"]
        if not OrderedDict or hasattr(self.fields, "keyOrder"):
            self.fields.keyOrder = field_order
        else:
            self.fields = OrderedDict((k, self.fields[k]) for k in field_order)


class LoginEmailForm(LoginForm):

    email = forms.EmailField(label=_("Email"))
    authentication_fail_message = _("O endereço de email ou senha não estão corretos.")
    identifier_field = "email"

    def __init__(self, *args, **kwargs):
        super(LoginEmailForm, self).__init__(*args, **kwargs)
        field_order = ["email", "password", "remember"]
        if not OrderedDict or hasattr(self.fields, "keyOrder"):
            self.fields.keyOrder = field_order
        else:
            self.fields = OrderedDict((k, self.fields[k]) for k in field_order)


class ChangePasswordForm(forms.Form):

    password_current = forms.CharField(
        label=_("Current Password"),
        widget=forms.PasswordInput(render_value=False)
    )
    password_new = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(render_value=False)
    )
    password_new_confirm = forms.CharField(
        label=_("New Password (again)"),
        widget=forms.PasswordInput(render_value=False)
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    def clean_password_current(self):
        if not self.user.check_password(self.cleaned_data.get("password_current")):
            raise forms.ValidationError(_("Por favor digite a sua senha."))
        return self.cleaned_data["password_current"]

    def clean_password_new_confirm(self):
        if "password_new" in self.cleaned_data and "password_new_confirm" in self.cleaned_data:
            if self.cleaned_data["password_new"] != self.cleaned_data["password_new_confirm"]:
                raise forms.ValidationError(_("Você deve digitar a mesma senha."))
        return self.cleaned_data["password_new_confirm"]


class PasswordResetForm(forms.Form):

    email = forms.EmailField(label=_("Email"), required=True)

    def clean_email(self):
        value = self.cleaned_data["email"]
        if not EmailAddress.objects.filter(email__iexact=value).exists():
            raise forms.ValidationError(_("Endereço de email não foi encontrado."))
        return value


class PasswordResetTokenForm(forms.Form):

    password = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(render_value=False)
    )
    password_confirm = forms.CharField(
        label=_("New Password (again)"),
        widget=forms.PasswordInput(render_value=False)
    )

    def clean_password_confirm(self):
        if "password" in self.cleaned_data and "password_confirm" in self.cleaned_data:
            if self.cleaned_data["password"] != self.cleaned_data["password_confirm"]:
                raise forms.ValidationError(_("Digite o mesmo email."))
        return self.cleaned_data["password_confirm"]


class SettingsForm(forms.Form):

    email = forms.EmailField(label=_("Email"), required=True)
    timezone = forms.ChoiceField(
        label=_("Timezone"),
        choices=[("", "---------")] + settings.ACCOUNT_TIMEZONES,
        required=False
    )
    bio = forms.CharField(label=_("bio"), max_length=100)
    if settings.USE_I18N:
        language = forms.ChoiceField(
            label=_("Language"),
            choices=settings.ACCOUNT_LANGUAGES,
            required=False
        )

    def clean_email(self):
        value = self.cleaned_data["email"]
        if self.initial.get("email") == value:
            return value
        qs = EmailAddress.objects.filter(email__iexact=value)
        if not qs.exists() or not settings.ACCOUNT_EMAIL_UNIQUE:
            return value
        raise forms.ValidationError(_("Um usuário já está registrado com este email."))