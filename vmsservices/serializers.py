from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import empty

from .activitylog import ACTIVITY_MODULES

class LoginSerializer(serializers.Serializer):

    login_id = serializers.CharField(
        required=True,
        max_length=150
    )


    password = serializers.CharField(
        required=True,
        write_only=True
    )


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(
        required=True
    )

class BlankableIntegerField(serializers.IntegerField):
    """Accepts 1, "1", "" or null. Blank or null becomes None."""

    def run_validation(self, data=empty):
        if data == "":
            data = None
        return super().run_validation(data)

class BlankableUUIDField(serializers.UUIDField):
    """Accepts UUID, UUID string, "" or null. Blank or null becomes None."""

    def run_validation(self, data=empty):
        if data == "":
            data = None
        return super().run_validation(data)

# role creation and update and list and delete
class RoleCreateSerializer(serializers.Serializer):
 
    name = serializers.CharField(max_length=150)
 
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )
 
    is_active = serializers.BooleanField(
        required=False,
        default=True
    )
 
 
class RoleUpdateSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
    name = serializers.CharField(max_length=150)
 
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )
 
    is_active = serializers.BooleanField(
        required=False,
        default=True
    )
 
 
class RoleDeleteSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
 
class RoleListSerializer(serializers.Serializer):
 
    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )
 
    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )


# role permission: get / save

class RolePermissionGetSerializer(serializers.Serializer):

    role_guid = serializers.UUIDField()


class PermissionItemSerializer(serializers.Serializer):

    menu_key = serializers.CharField(max_length=200)

    view = serializers.BooleanField()

    enabled = serializers.BooleanField()


class RolePermissionSaveSerializer(serializers.Serializer):

    role_guid = serializers.UUIDField()

    permissions = PermissionItemSerializer(many=True)

# user creation and update and list and delete
# create / update are sent as multipart/form-data (profile photo upload).
# NOTE: with multipart, a missing boolean is read as False, so the frontend
# always sends is_active explicitly.

GENDER_CHOICES = ["Male", "Female"]
PHONE_REGEX = r"^\+?[0-9\s\-]{7,20}$"

MAX_USER_PHOTO_SIZE = 2 * 1024 * 1024  # 2 MB


def _check_photo_size(value):
    if value.size > MAX_USER_PHOTO_SIZE:
        raise serializers.ValidationError("Photo must be 2 MB or smaller")
    return value


def _run_password_validators(value):
    try:
        password_validation.validate_password(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages))
    return value


class UserCreateSerializer(serializers.Serializer):

    login_id = serializers.CharField(max_length=150)

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    first_name = serializers.CharField(max_length=100)

    last_name = serializers.CharField(max_length=100)

    email = serializers.EmailField(max_length=254)

    job_title = serializers.CharField(max_length=150)

    gender = serializers.ChoiceField(
        choices=GENDER_CHOICES,
        required=False,
        allow_blank=True,
        default=""
    )

    role = serializers.UUIDField()            # guid of Role

    site = BlankableUUIDField(                # guid of Site (optional)
        required=False,
        allow_null=True,
        default=None,
    )

    is_active = serializers.BooleanField(
        required=False,
        default=True
    )

    profile_photo = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_password(self, value):
        return _run_password_validators(value)

    def validate_profile_photo(self, value):
        if value is None:
            return value
        return _check_photo_size(value)


class UserUpdateSerializer(serializers.Serializer):

    # request field is "id"; the service receives it as user_id
    id = serializers.IntegerField(source="user_id")

    login_id = serializers.CharField(max_length=150)

    # Optional on update: blank or missing keeps the current password.
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        trim_whitespace=False,
        default=""
    )

    first_name = serializers.CharField(max_length=100)

    last_name = serializers.CharField(max_length=100)

    email = serializers.EmailField(max_length=254)

    job_title = serializers.CharField(max_length=150)

    gender = serializers.ChoiceField(
        choices=GENDER_CHOICES,
        required=False,
        allow_blank=True,
        default=""
    )

    role = serializers.UUIDField()

    site = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    is_active = serializers.BooleanField(
        required=False,
        default=True
    )

    # Optional on update: if not sent, the existing photo is kept.
    profile_photo = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_password(self, value):
        if not value:
            return value
        return _run_password_validators(value)

    def validate_profile_photo(self, value):
        if value is None:
            return value
        return _check_photo_size(value)


class UserDeleteSerializer(serializers.Serializer):

    id = serializers.IntegerField(source="user_id")


class UserListSerializer(serializers.Serializer):

    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

# site type creation and update and list and delete

class SiteTypeCreateSerializer(serializers.Serializer):

    site_type = serializers.CharField(max_length=150)

    site_type_description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )


class SiteTypeUpdateSerializer(serializers.Serializer):

    guid = serializers.UUIDField()

    site_type = serializers.CharField(max_length=150)

    site_type_description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )


class SiteTypeDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class SiteTypeListSerializer(serializers.Serializer):

    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )



# site model creation and update and list and delete
class SiteModelCreateSerializer(serializers.Serializer):
 
    site_model = serializers.CharField(max_length=150)
 
    site_model_description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )
 
 
class SiteModelUpdateSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
    site_model = serializers.CharField(max_length=150)
 
    site_model_description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )
 
 
class SiteModelDeleteSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
 
class SiteModelListSerializer(serializers.Serializer):
 
    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )
 
    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )




# category creation and update and list and delete
class CategoryCreateSerializer(serializers.Serializer):

    category_name = serializers.CharField(max_length=150)



class CategoryUpdateSerializer(serializers.Serializer):

    guid = serializers.UUIDField()

    category_name = serializers.CharField(max_length=150)



class CategoryDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class CategoryListSerializer(serializers.Serializer):

    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )





# site creation and update and list and delete
MAX_SITE_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
 
 
def _check_image_size(value):
    if value.size > MAX_SITE_IMAGE_SIZE:
        raise serializers.ValidationError("Image must be 5 MB or smaller")
    return value
 
 
class SiteCreateSerializer(serializers.Serializer):
 
    site_code = serializers.CharField(max_length=50)
 
    site_name = serializers.CharField(max_length=150)
 
    site_model = serializers.UUIDField()      # guid of Site Model
 
    site_type = serializers.UUIDField()       # guid of Site Type
 
    category = serializers.UUIDField()        # guid of Category

    parent = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )
 
    contact = serializers.CharField(max_length=100)
 
    site_image = serializers.ImageField()
 
    address = serializers.CharField()
 
    def validate_site_image(self, value):
        return _check_image_size(value)
 
 
class SiteUpdateSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
    site_code = serializers.CharField(max_length=50)
 
    site_name = serializers.CharField(max_length=150)
 
    site_model = serializers.UUIDField()
 
    site_type = serializers.UUIDField()
 
    category = serializers.UUIDField()

    parent = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )
 
    contact = serializers.CharField(max_length=100)
 
    # Optional on update: if not sent, the existing image is kept.
    site_image = serializers.ImageField(
        required=False,
        allow_null=True
    )
 
    address = serializers.CharField()
 
    def validate_site_image(self, value):
        if value is None:
            return value
        return _check_image_size(value)
 
 
class SiteDeleteSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
 
class SiteListSerializer(serializers.Serializer):
 
    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )
 
    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    site_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    site_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    

class SiteParentListSerializer(serializers.Serializer):
 
    exclude = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )    






# tenant creation and update and list and delete

class TenantCreateSerializer(serializers.Serializer):

    first_name = serializers.CharField(max_length=100)

    last_name = serializers.CharField(max_length=100)

    contact = serializers.CharField(max_length=20)

    email = serializers.EmailField(max_length=254)

    tenant_name = serializers.CharField(max_length=150)

    block = serializers.CharField(max_length=50)

    floor = serializers.CharField(max_length=50)

    unit = serializers.CharField(max_length=50)

    site = serializers.UUIDField()            # guid of Site


class TenantUpdateSerializer(TenantCreateSerializer):

    guid = serializers.UUIDField()


class TenantDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class TenantListSerializer(serializers.Serializer):

    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    site_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    site_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )



# identity type creation and update and list and delete

VALIDATION_CHOICES = ["Required", "Optional", "Not Required"]


class IdentityTypeCreateSerializer(serializers.Serializer):

    identity_type_name = serializers.CharField(max_length=150)

    identity_number_validation = serializers.ChoiceField(choices=VALIDATION_CHOICES)

    identity_number_digits = BlankableIntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )

    identity_number_alphabets = BlankableIntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )

    identity_number_format = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )

    phone_number_validation = serializers.ChoiceField(choices=VALIDATION_CHOICES)

    phone_number_min = BlankableIntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )

    phone_number_max = BlankableIntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )

    phone_number_starting_with = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )

    phone_number_format = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        low = attrs.get("phone_number_min")
        high = attrs.get("phone_number_max")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {"phone_number_min": "Minimum digits cannot be greater than maximum digits"}
            )
        return attrs


class IdentityTypeUpdateSerializer(IdentityTypeCreateSerializer):

    guid = serializers.UUIDField()


class IdentityTypeDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class IdentityTypeListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    search = serializers.CharField(required=False, allow_blank=True, default="")





# key creation and update and list and delete
 
KEY_STATUS_VALUES = ["Assigned", "Available", "Lost"]
 
 
class KeyCreateSerializer(serializers.Serializer):
 
    key_no = serializers.CharField(max_length=50)
 
    key_name = serializers.CharField(max_length=150)
 
    site = serializers.UUIDField()            # guid of Site
 
    status = serializers.ChoiceField(
        choices=KEY_STATUS_VALUES,
        required=False,
        default="Available"
    )
 
 
class KeyUpdateSerializer(KeyCreateSerializer):
 
    guid = serializers.UUIDField()
 
 
class KeyDeleteSerializer(serializers.Serializer):
 
    guid = serializers.UUIDField()
 
 
class KeyListSerializer(serializers.Serializer):
 
    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )
 
    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )
 
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
 
    site_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )
 
    status = serializers.ChoiceField(
        choices=KEY_STATUS_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )
 

# visitor type creation and update and list and delete

class VisitorTypeCreateSerializer(serializers.Serializer):

    name = serializers.CharField(max_length=150)

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

    is_active = serializers.BooleanField(
        required=False,
        default=True
    )


class VisitorTypeUpdateSerializer(serializers.Serializer):

    guid = serializers.UUIDField()

    name = serializers.CharField(max_length=150)

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

    # No default on update: if not sent, the current status is kept.
    is_active = serializers.BooleanField(required=False)


class VisitorTypeDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class VisitorTypeListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    search = serializers.CharField(required=False, allow_blank=True, default="")




# Append this to serializers.py

# pass creation and update and list and delete

PASS_STATUS_VALUES = ["Active", "Assigned", "Lost"]


class PassCreateSerializer(serializers.Serializer):

    pass_no = serializers.CharField(max_length=50)

    pass_name = serializers.CharField(max_length=150)

    site = serializers.UUIDField()            # guid of Site

    visitor_type = serializers.UUIDField()    # guid of VisitorType

    status = serializers.ChoiceField(
        choices=PASS_STATUS_VALUES,
        required=False,
        default="Active"
    )


class PassUpdateSerializer(PassCreateSerializer):

    guid = serializers.UUIDField()


class PassDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class PassListSerializer(serializers.Serializer):

    page = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    page_size = BlankableIntegerField(
        required=False,
        allow_null=True,
    )

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    site_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    status = serializers.ChoiceField(
        choices=PASS_STATUS_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )

    visitor_type_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )



# >>> Append this block to the END of serializers.py <<<
# (uses BlankableIntegerField / BlankableUUIDField already defined earlier in the file)

# tenant notification creation and update and list and delete

class TenantNotificationCreateSerializer(serializers.Serializer):

    site = serializers.UUIDField()            # guid of Site

    tenant = serializers.UUIDField()          # guid of Tenant (the "location")

    from_date = serializers.DateField()

    to_date = serializers.DateField()

    message = serializers.CharField()

    def validate(self, attrs):
        if attrs["to_date"] < attrs["from_date"]:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


class TenantNotificationUpdateSerializer(TenantNotificationCreateSerializer):

    guid = serializers.UUIDField()


class TenantNotificationDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


# class TenantNotificationListSerializer(serializers.Serializer):

#     page = BlankableIntegerField(
#         required=False,
#         allow_null=True,
#     )

#     page_size = BlankableIntegerField(
#         required=False,
#         allow_null=True,
#     )

#     search = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         default="",
#     )

#     site_guid = BlankableUUIDField(
#         required=False,
#         allow_null=True,
#         default=None,
#     )



class TenantNotificationListSerializer(serializers.Serializer):
    # ...unchanged, exactly as above...
    site_guid = BlankableUUIDField(
        required=False,
        allow_null=True,
        default=None,
    )


class TenantAvailabilityCheckSerializer(serializers.Serializer):

    tenant = serializers.UUIDField()          # guid of Tenant (the "location")

    from_date = serializers.DateField()

    to_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["to_date"] < attrs["from_date"]:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs



# >>> Append this block to the END of serializers.py <<<
# (uses BlankableIntegerField / BlankableUUIDField already defined earlier)

# visitor / contractor check-in, list, check-out, identity search

VISIT_KIND_VALUES = ["Visitor", "Contractor"]


class BlankableDateField(serializers.DateField):
    """Accepts a date string, "" or null. Blank or null becomes None."""

    def run_validation(self, data=empty):
        if data == "":
            data = None
        return super().run_validation(data)


class VisitorCheckInSerializer(serializers.Serializer):

    kind = serializers.ChoiceField(choices=VISIT_KIND_VALUES)

    site = serializers.UUIDField()                # guid of Site

    location = serializers.UUIDField()            # guid of Tenant

    # If the person was picked from the identity search, send their id.
    person_id = BlankableIntegerField(required=False, allow_null=True, default=None)

    person_name = serializers.CharField(max_length=150)

    identity_type = serializers.CharField(max_length=150)

    identity_number = serializers.CharField(max_length=100)

    phone_number = serializers.CharField(max_length=20)

    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True, default="")

    company = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    company_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    pass_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    key_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    vehicle_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    remark = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["kind"] == "Contractor":
            errors = {}
            if not attrs.get("company", "").strip():
                errors["company"] = "Company name is required for a contractor"
            if not attrs.get("company_phone", "").strip():
                errors["company_phone"] = "Company phone number is required for a contractor"
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class VisitorCheckOutSerializer(serializers.Serializer):

    kind = serializers.ChoiceField(choices=VISIT_KIND_VALUES)

    guid = serializers.UUIDField()


class VisitorIdentitySearchSerializer(serializers.Serializer):

    identity_type = serializers.CharField(max_length=150)
    identity_number = serializers.CharField(max_length=100)
    site = BlankableUUIDField(required=False, allow_null=True, default=None)

class VisitorListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    # matches identity number, name, contact, location, vehicle number,
    # email, company and company phone number
    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # "" / missing = both tables
    kind = serializers.ChoiceField(
        choices=VISIT_KIND_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )

    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs

# find the checked-in visitor / contractor holding a pass (check-out modal)

class VisitorPassLookupSerializer(serializers.Serializer):

    site = serializers.UUIDField()            # guid of Site

    pass_no = serializers.CharField(max_length=50)







# >>> Append this block to the END of serializers.py <<<
# (uses BlankableIntegerField / BlankableUUIDField / BlankableDateField defined earlier)

# ban creation and update and list and delete

BAN_TYPE_VALUES = ["TEMPORARY", "PERMANENT"]

# Status is computed, not stored: Lifted / Active / Upcoming / Expired
BAN_STATUS_VALUES = ["Active", "Upcoming", "Expired", "Lifted"]


def _validate_ban_dates(attrs):
    """TEMPORARY needs from + to dates. PERMANENT clears both."""
    if attrs["ban_type"] == "TEMPORARY":
        errors = {}
        if not attrs.get("from_date"):
            errors["from_date"] = "From Date is required for a temporary ban"
        if not attrs.get("to_date"):
            errors["to_date"] = "To Date is required for a temporary ban"
        if errors:
            raise serializers.ValidationError(errors)
        if attrs["to_date"] < attrs["from_date"]:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
    else:
        attrs["from_date"] = None
        attrs["to_date"] = None
    return attrs


class BanCreateSerializer(serializers.Serializer):

    person_id = serializers.IntegerField()

    # guids of the sites to ban the person at (one ban row per site)
    sites = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )

    ban_type = serializers.ChoiceField(choices=BAN_TYPE_VALUES)

    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    reason = serializers.CharField()

    def validate_sites(self, value):
        return list(dict.fromkeys(value))  # drop duplicates, keep order

    def validate(self, attrs):
        return _validate_ban_dates(attrs)


class BanUpdateSerializer(serializers.Serializer):

    guid = serializers.UUIDField()

    site = serializers.UUIDField()            # guid of Site

    ban_type = serializers.ChoiceField(choices=BAN_TYPE_VALUES)

    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    reason = serializers.CharField()

    # No default: if not sent, the current value is kept.
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        return _validate_ban_dates(attrs)


class BanDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class BanLiftSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


class BanListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    # matches name, phone, email, identity type, identity number
    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    ban_type = serializers.ChoiceField(
        choices=BAN_TYPE_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )

    status = serializers.ChoiceField(
        choices=BAN_STATUS_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )

    # bans whose period overlaps this range (permanent bans always overlap)
    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


# approver dropdown
class ApproverListSerializer(serializers.Serializer):

    site_guid = serializers.UUIDField()




# =====================================================================
# serializers.py  -  APPEND this block to the END of the file.
# (BlankableIntegerField / BlankableUUIDField / BlankableDateField and
#  ApproverListSerializer are already defined above in your file.)
# =====================================================================

# ---------------------------------------------------------------------
# pre-registration: create / update / delete / list
# ---------------------------------------------------------------------

class BlankableTimeField(serializers.TimeField):
    """Accepts "09:00", "09:00:00", "" or null. Blank or null becomes None."""

    def run_validation(self, data=empty):
        if data == "":
            data = None
        return super().run_validation(data)


class PreRegistrationCreateSerializer(serializers.Serializer):

    site = serializers.UUIDField()                # guid of Site

    location = serializers.UUIDField()            # guid of Tenant

    # "Type of Visitor". The server decides Visitor / Contractor from it.
    visitor_type = serializers.UUIDField()        # guid of VisitorType

    from_date = serializers.DateField()

    to_date = serializers.DateField()

    from_time = BlankableTimeField(required=False, allow_null=True, default=None)

    to_time = BlankableTimeField(required=False, allow_null=True, default=None)

    # If the person was picked from the identity search, send their id.
    person_id = BlankableIntegerField(required=False, allow_null=True, default=None)

    person_name = serializers.CharField(max_length=150)

    identity_type = serializers.CharField(max_length=150)

    identity_number = serializers.CharField(max_length=100)

    # The identity type decides whether the phone is Required / Optional / Not Required
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )

    email = serializers.EmailField(
        required=False, allow_blank=True, allow_null=True, default=""
    )

    company = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )

    company_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )

    pass_no = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )

    key_no = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )

    vehicle_number = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )

    remark = serializers.CharField(required=False, allow_blank=True, default="")

    approver_email = serializers.EmailField()

    def validate(self, attrs):
        f, t = attrs["from_date"], attrs["to_date"]
        if t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )

        ft, tt = attrs.get("from_time"), attrs.get("to_time")
        if bool(ft) != bool(tt):
            raise serializers.ValidationError(
                {"to_time": "Provide both From Time and To Time, or neither"}
            )
        if ft and tt and f == t and tt <= ft:
            raise serializers.ValidationError(
                {"to_time": "To Time must be after From Time"}
            )
        return attrs


class PreRegistrationUpdateSerializer(PreRegistrationCreateSerializer):

    guid = serializers.UUIDField()


class PreRegistrationDeleteSerializer(serializers.Serializer):

    guid = serializers.UUIDField()


PRE_REG_STATUS_VALUES = ["PENDING", "APPROVED", "REJECTED"]


class _StatusFilterMixin(serializers.Serializer):
    """Accepts Pending / pending / PENDING ... and normalises to upper case."""

    status = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, value):
        value = (value or "").strip().upper()
        if value and value not in PRE_REG_STATUS_VALUES:
            raise serializers.ValidationError("Invalid status")
        return value


class PreRegistrationListSerializer(_StatusFilterMixin):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    # matches name, identity number, phone, email, location, company, approver
    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    visitor_type_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # requests whose visit period overlaps this range
    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


# ---------------------------------------------------------------------
# approval: list / approve / reject
# ---------------------------------------------------------------------

class ApprovalListSerializer(serializers.Serializer):
    """Approval page: pending requests only (no status filter)."""

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    visitor_type_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # requests whose visit period overlaps this range
    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


class ApprovalHistoryListSerializer(serializers.Serializer):
    """History tab: approved + rejected requests."""

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    visitor_type_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # "" = both. Accepts Approved / approved / APPROVED ...
    decision = serializers.CharField(required=False, allow_blank=True, default="")

    # the day the request was approved / rejected
    decided_from = BlankableDateField(required=False, allow_null=True, default=None)

    decided_to = BlankableDateField(required=False, allow_null=True, default=None)

    def validate_decision(self, value):
        value = (value or "").strip().upper()
        if value and value not in ("APPROVED", "REJECTED"):
            raise serializers.ValidationError("Invalid decision")
        return value

    def validate(self, attrs):
        f, t = attrs.get("decided_from"), attrs.get("decided_to")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"decided_to": "To Date cannot be before From Date"}
            )
        return attrs


class ApprovalActionSerializer(serializers.Serializer):

    guid = serializers.UUIDField()

    action = serializers.ChoiceField(choices=["APPROVE", "REJECT"])

    remark = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["action"] == "REJECT" and not attrs.get("remark", "").strip():
            raise serializers.ValidationError(
                {"remark": "Reason is required when rejecting a request"}
            )
        return attrs


class ApprovalBulkActionSerializer(serializers.Serializer):

    bulk_id = serializers.CharField(max_length=50)

    action = serializers.ChoiceField(choices=["APPROVE", "REJECT"])

    remark = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["action"] == "REJECT" and not attrs.get("remark", "").strip():
            raise serializers.ValidationError(
                {"remark": "Reason is required when rejecting a request"}
            )
        return attrs


# ---------------------------------------------------------------------
# pre-registration APPROVED page: list / check-in
# ---------------------------------------------------------------------

PRE_REG_VISIT_STATUS_VALUES = ["Pending", "Checked In", "Checked Out"]


class PreRegistrationApprovedListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    kind = serializers.ChoiceField(
        choices=VISIT_KIND_VALUES, required=False, allow_blank=True, default=""
    )

    visit_status = serializers.ChoiceField(
        choices=PRE_REG_VISIT_STATUS_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )

    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


class PreRegistrationCheckInSerializer(serializers.Serializer):

    kind = serializers.ChoiceField(choices=VISIT_KIND_VALUES)

    guid = serializers.UUIDField()

    pass_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    key_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    vehicle_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")



# ---------------------------------------------------------------------
# report: check-in / check-out list
# ---------------------------------------------------------------------

# class ReportListSerializer(serializers.Serializer):

#     # page / page_size null = return all rows (used by CSV export)
#     page = BlankableIntegerField(required=False, allow_null=True)

#     page_size = BlankableIntegerField(required=False, allow_null=True)

#     # matches name, phone number, company, identity number, email
#     search = serializers.CharField(required=False, allow_blank=True, default="")

#     site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

#     visitor_type_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

#     # filters on the check-in date
#     from_date = BlankableDateField(required=False, allow_null=True, default=None)

#     to_date = BlankableDateField(required=False, allow_null=True, default=None)

#     def validate(self, attrs):
#         f, t = attrs.get("from_date"), attrs.get("to_date")
#         if f and t and t < f:
#             raise serializers.ValidationError(
#                 {"to_date": "To Date cannot be before From Date"}
#             )
#         return attrs


class ReportListSerializer(serializers.Serializer):

    # page / page_size null = return all rows (used by export)
    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    # matches name, phone number, company, identity number, email
    search = serializers.CharField(required=False, allow_blank=True, default="")

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    visitor_type_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # filters on the check-in date
    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    # export flag: not sent / null = normal JSON list
    #              true = Excel file, false = PDF file
    isexcel = serializers.BooleanField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs



# ---------------------------------------------------------------------
# bulk pre-registration: validate / create / approved list / bulk ids
# ---------------------------------------------------------------------

BULK_MAX_ROWS = 200

_ROW_TEXT = dict(required=False, allow_blank=True, allow_null=True, default="")


class BulkPreRegistrationRowSerializer(serializers.Serializer):
    """One Excel row. Fields are lenient on purpose: a bad row must come back
    as a row error, not as a 400 for the whole file."""

    row_no = serializers.IntegerField(required=False, default=0)  # Excel row number
    person_name = serializers.CharField(**_ROW_TEXT)
    identity_type = serializers.CharField(**_ROW_TEXT)
    identity_number = serializers.CharField(**_ROW_TEXT)
    phone_number = serializers.CharField(**_ROW_TEXT)
    email = serializers.CharField(**_ROW_TEXT)
    company = serializers.CharField(**_ROW_TEXT)
    company_phone = serializers.CharField(**_ROW_TEXT)
    vehicle_number = serializers.CharField(**_ROW_TEXT)
    remark = serializers.CharField(**_ROW_TEXT)


class BulkPreRegistrationValidateSerializer(serializers.Serializer):

    # chosen once on the page, applies to every row
    site = serializers.UUIDField()                # guid of Site
    location = serializers.UUIDField()            # guid of Tenant
    visitor_type = serializers.UUIDField()        # guid of VisitorType
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    from_time = BlankableTimeField(required=False, allow_null=True, default=None)
    to_time = BlankableTimeField(required=False, allow_null=True, default=None)
    approver_email = serializers.EmailField()

    rows = BulkPreRegistrationRowSerializer(many=True, allow_empty=False)

    def validate_rows(self, value):
        if len(value) > BULK_MAX_ROWS:
            raise serializers.ValidationError(
                f"A maximum of {BULK_MAX_ROWS} rows is allowed per upload"
            )
        return value

    def validate(self, attrs):
        f, t = attrs["from_date"], attrs["to_date"]
        if t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        ft, tt = attrs.get("from_time"), attrs.get("to_time")
        if bool(ft) != bool(tt):
            raise serializers.ValidationError(
                {"to_time": "Provide both From Time and To Time, or neither"}
            )
        if ft and tt and f == t and tt <= ft:
            raise serializers.ValidationError(
                {"to_time": "To Time must be after From Time"}
            )
        return attrs


class BulkPreRegistrationCreateSerializer(BulkPreRegistrationValidateSerializer):
    """Same payload as validate. The server validates again before saving."""


class BulkPreRegistrationApprovedListSerializer(serializers.Serializer):

    page = BlankableIntegerField(required=False, allow_null=True)
    page_size = BlankableIntegerField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # "" = every bulk upload
    bulk_id = serializers.CharField(required=False, allow_blank=True, default="")

    kind = serializers.ChoiceField(
        choices=VISIT_KIND_VALUES, required=False, allow_blank=True, default=""
    )
    visit_status = serializers.ChoiceField(
        choices=PRE_REG_VISIT_STATUS_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )
    from_date = BlankableDateField(required=False, allow_null=True, default=None)
    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


class BulkIdListSerializer(serializers.Serializer):

    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)
    search = serializers.CharField(required=False, allow_blank=True, default="")


class PreRegistrationBulkCheckInSerializer(serializers.Serializer):

    bulk_id = serializers.CharField(max_length=50)

    pass_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    key_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class PreRegistrationBulkCheckOutSerializer(serializers.Serializer):

    bulk_id = serializers.CharField(max_length=50)



# >>> Append this block to the END of serializers.py <<<
# (uses BlankableIntegerField / BlankableUUIDField / BlankableDateField and
#  VISIT_KIND_VALUES, all defined earlier in the file)

# ---------------------------------------------------------------------
# dashboard: summary + not-checked-out list
# ---------------------------------------------------------------------

class DashboardSummarySerializer(serializers.Serializer):

    # null / "" = all sites (super admin) or own site (normal user)
    site_guid = BlankableUUIDField(required=False, allow_null=True, default=None)

    # check-in / check-out date range. Missing = last 30 days.
    from_date = BlankableDateField(required=False, allow_null=True, default=None)

    to_date = BlankableDateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        f, t = attrs.get("from_date"), attrs.get("to_date")
        if f and t and t < f:
            raise serializers.ValidationError(
                {"to_date": "To Date cannot be before From Date"}
            )
        return attrs


class DashboardNotCheckedOutSerializer(DashboardSummarySerializer):

    page = BlankableIntegerField(required=False, allow_null=True)

    page_size = BlankableIntegerField(required=False, allow_null=True)

    # matches name, identity number, phone, company, location, pass number
    search = serializers.CharField(required=False, allow_blank=True, default="")

    # "" = both visitors and contractors
    kind = serializers.ChoiceField(
        choices=VISIT_KIND_VALUES,
        required=False,
        allow_blank=True,
        default="",
    )


# ---------------------------------------------------------------------
# activity logs: list
# ---------------------------------------------------------------------

class LogListSerializer(serializers.Serializer):

    menu = serializers.ChoiceField(choices=ACTIVITY_MODULES)

    date = BlankableDateField(required=False, allow_null=True, default=None)