import uuid


from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):

    def create_user(self, login_id, email, password=None, **extra_fields):

        if not login_id:
            raise ValueError("Login ID is required")

        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)

        user = self.model(
            login_id=login_id,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, login_id, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            login_id=login_id,
            email=email,
            password=password,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):

    login_id = models.CharField(
        max_length=150,
        unique=True
    )

    email = models.EmailField(
        unique=True
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    job_title = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    gender = models.CharField(
        max_length=10,
        blank=True,
        default=""
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default=""
    )


    profile_photo = models.ImageField(
        upload_to="user_photos/%Y/%m/",
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    is_staff = models.BooleanField(
        default=False
    )

    role = models.ForeignKey(
        "Role",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users"
    )

    # Site this user belongs to (Site is defined further down in this file)
    site = models.ForeignKey(
        "Site",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    objects = UserManager()

    USERNAME_FIELD = "login_id"

    REQUIRED_FIELDS = ["email"]

    def is_super_admin(self):
        return (
            self.is_active
            and self.is_staff
            and self.is_superuser
        )

    def get_user_details(self):
        return {
            "user_id": self.id,
            "login_id": self.login_id,
            "email": self.email,
            "is_active": self.is_active,
            "is_staff": self.is_staff,
            "is_superuser": self.is_superuser,
        }

    def __str__(self):
        return self.login_id





class LoginHistory(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_history"
    )

    login_id = models.CharField(
        max_length=150
    )

    refresh_jti = models.CharField(
        max_length=255,
        unique=True
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        blank=True,
        default=""
    )

    login_at = models.DateTimeField(
        auto_now_add=True
    )

    logout_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.login_id} - {self.login_at}"
        


# role creation and update and list and delete
 
class Role(models.Model):
 
    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
 
    name = models.CharField(
        max_length=150,
        unique=True
    )
 
    description = models.TextField(
        blank=True,
        default=""
    )
 
    is_active = models.BooleanField(
        default=True
    )
 
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_roles"
    )
 
    created_at = models.DateTimeField(
        auto_now_add=True
    )
 
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_roles"
    )
 
    updated_at = models.DateTimeField(
        auto_now=True
    )
 
    def __str__(self):
        return self.name


# role permission: sidebar menu access + sub-site list access per role


class RolePermission(models.Model):

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permissions"
    )

    menu_key = models.CharField(
        max_length=200
    )

    menu_enabled = models.BooleanField(
        default=False
    )

    can_view_subsites = models.BooleanField(
        default=False
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_role_permissions"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        unique_together = ("role", "menu_key")

    def __str__(self):
        return f"{self.role.name} - {self.menu_key}"

# site Type creation and update and list and delete

class SiteType(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    site_type = models.CharField(
        max_length=150,
        unique=True
    )

    site_type_description = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_site_types"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_types"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.site_type



# site Model creation and update and list and delete
 
class SiteModel(models.Model):
 
    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
 
    site_model = models.CharField(
        max_length=150,
        unique=True
    )
 
    site_model_description = models.TextField(
        blank=True,
        default=""
    )
 
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_site_models"
    )
 
    created_at = models.DateTimeField(
        auto_now_add=True
    )
 
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_models"
    )
 
    updated_at = models.DateTimeField(
        auto_now=True
    )
 
    def __str__(self):
        return self.site_model



# category creation and update and list and delete

class Category(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    category_name = models.CharField(
        max_length=150,
        unique=True
    )



    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_categories"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_categories"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.category_name





# site creation and update and list and delete
 
class Site(models.Model):
 
    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
 
    site_code = models.CharField(
        max_length=50,
        unique=True
    )
 
    site_name = models.CharField(
        max_length=150
    )
 
    site_model = models.ForeignKey(
        SiteModel,
        on_delete=models.PROTECT,
        related_name="sites"
    )
 
    site_type = models.ForeignKey(
        SiteType,
        on_delete=models.PROTECT,
        related_name="sites"
    )
 
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="sites"
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subsites",
    )
 
    contact = models.CharField(
        max_length=100
    )
 
    site_image = models.ImageField(
        upload_to="site_images/%Y/%m/"
    )
 
    address = models.TextField()
 
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sites"
    )
 
    created_at = models.DateTimeField(
        auto_now_add=True
    )
 
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_sites"
    )
 
    updated_at = models.DateTimeField(
        auto_now=True
    )
 
    def __str__(self):
        return f"{self.site_code} - {self.site_name}"




# tenant creation and update and list and delete

class Tenant(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    first_name = models.CharField(max_length=100)

    last_name = models.CharField(max_length=100)

    contact = models.CharField(max_length=20)

    email = models.EmailField()

    tenant_name = models.CharField(max_length=150)

    block = models.CharField(max_length=50)

    floor = models.CharField(max_length=50)

    unit = models.CharField(max_length=50)

    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="tenants"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenants"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenants"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant_name} - {self.unit}"




# identity type creation and update and list and delete

class IdentityType(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    identity_type_name = models.CharField(max_length=150, unique=True)

    # Required / Optional / Not Required
    identity_number_validation = models.CharField(max_length=20)
    identity_number_digits = models.PositiveIntegerField(null=True, blank=True)
    identity_number_alphabets = models.PositiveIntegerField(null=True, blank=True)
    identity_number_format = models.CharField(max_length=100, blank=True, default="")

    phone_number_validation = models.CharField(max_length=20)
    phone_number_min = models.PositiveIntegerField(null=True, blank=True)
    phone_number_max = models.PositiveIntegerField(null=True, blank=True)
    phone_number_starting_with = models.CharField(max_length=50, blank=True, default="")
    phone_number_format = models.CharField(max_length=100, blank=True, default="")

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_identity_types"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_identity_types"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.identity_type_name




# key creation and update and list and delete
 
KEY_STATUS_CHOICES = [
    ("Assigned", "Assigned"),
    ("Available", "Available"),
    ("Lost", "Lost"),
]
 
 
class Key(models.Model):
 
    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
 
    key_no = models.CharField(
        max_length=50
    )
 
    key_name = models.CharField(
        max_length=150
    )
 
    # Every key belongs to exactly one site
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="keys"
    )
 
    status = models.CharField(
        max_length=20,
        choices=KEY_STATUS_CHOICES,
        default="Available"
    )
 
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_keys"
    )
 
    created_at = models.DateTimeField(
        auto_now_add=True
    )
 
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_keys"
    )
 
    updated_at = models.DateTimeField(
        auto_now=True
    )
 
    class Meta:
        # the same key number can exist in different sites, but not twice in one site
        unique_together = ("site", "key_no")
 
    def __str__(self):
        return f"{self.key_no} - {self.key_name}"


# visitor type creation and update and list and delete

class VisitorType(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    name = models.CharField(
        max_length=150,
        unique=True
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    is_active = models.BooleanField(
        default=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_visitor_types"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_visitor_types"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


# Append this to models.py (after the VisitorType class)

# pass creation and update and list and delete

PASS_STATUS_CHOICES = [
    ("Active", "Active"),
    ("Assigned", "Assigned"),
    ("Lost", "Lost"),
]


class Pass(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    pass_no = models.CharField(
        max_length=50
    )

    pass_name = models.CharField(
        max_length=150
    )

    # Every pass belongs to exactly one site
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="passes"
    )

    visitor_type = models.ForeignKey(
        "VisitorType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="passes"
    )

    status = models.CharField(
        max_length=20,
        choices=PASS_STATUS_CHOICES,
        default="Active"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_passes"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_passes"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        # the same pass number can exist in different sites, but not twice in one site
        unique_together = ("site", "pass_no")

    def __str__(self):
        return f"{self.pass_no} - {self.pass_name}"


# >>> Append this block to the END of models.py <<<

# tenant notification creation and update and list and delete

class TenantNotification(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    # Every notification belongs to exactly one site
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="tenant_notifications"
    )

    # The tenant/location the notification is addressed to
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="notifications"
    )

    from_date = models.DateField()

    to_date = models.DateField()

    message = models.TextField()

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_notifications"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenant_notifications"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.tenant_name} - {self.from_date} to {self.to_date}"




# >>> Append this block to the END of models.py <<<

# visitor details (one row per person) + visitor / contractor visit tables

VISIT_SOURCE_CHOICES = [
    ("WALK_IN", "WALK_IN"),
    ("PRE_REGISTRATION", "PRE_REGISTRATION"),
    ("PRE_REGISTRATION_BULK", "PRE_REGISTRATION_BULK"),
]

APPROVAL_STATUS_CHOICES = [
    ("PENDING", "PENDING"),
    ("APPROVED", "APPROVED"),
    ("REJECTED", "REJECTED"),
]


class VisitorDetail(models.Model):
    """One row per person. The same identity number may repeat
    (e.g. FOREIGN_IC 1245Y for two different people), so it is NOT unique."""

    person_name = models.CharField(max_length=150)

    identity_type = models.CharField(max_length=150)

    identity_number = models.CharField(max_length=100, db_index=True)

    phone_number = models.CharField(max_length=20, blank=True, default="")

    email = models.EmailField(null=True, blank=True, unique=True)

    currently_checked_in = models.BooleanField(default=False)

    is_banned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.person_name} ({self.identity_type} {self.identity_number})"


class VisitRecordBase(models.Model):
    """Columns shared by the Visitor and Contractor tables."""

    guid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    person = models.ForeignKey(
        VisitorDetail,
        on_delete=models.PROTECT,
        related_name="%(class)s_records",
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="%(class)s_records",
    )

    # "Location" in the UI = the tenant of the site
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_records",
    )

    company = models.CharField(max_length=150, blank=True, default="")

    company_phone = models.CharField(max_length=20, blank=True, default="")

    source = models.CharField(
        max_length=30,
        choices=VISIT_SOURCE_CHOICES,
        default="WALK_IN",
    )

    bulk_id = models.CharField(max_length=50, null=True, blank=True)

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        null=True,
        blank=True,
    )

    # ===================== NEW CODE START =====================
    # which visitor type was chosen on the pre-registration form
    visitor_type = models.ForeignKey(
        "VisitorType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_records",
    )

    # who approved / rejected, when, and why (feeds the History tab)
    # approved_by = models.ForeignKey(
    #     User,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="decided_%(class)s_records",
    # )

    # approved_at = models.DateTimeField(null=True, blank=True)

    # approval_remark = models.TextField(blank=True, default="")


        # who approved / rejected, when, and why (feeds the History tab)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_%(class)s_records",
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    approval_remark = models.TextField(blank=True, default="")
    # ===================== NEW CODE END =======================

    requester_email = models.EmailField(null=True, blank=True)
    approver_email = models.EmailField(null=True, blank=True)
    from_date = models.DateField(null=True, blank=True)

    to_date = models.DateField(null=True, blank=True)

    from_time = models.TimeField(null=True, blank=True)

    to_time = models.TimeField(null=True, blank=True)

    check_in = models.DateTimeField(null=True, blank=True)

    check_out = models.DateTimeField(null=True, blank=True)

    pass_no = models.CharField(max_length=50, blank=True, default="")

    key_no = models.CharField(max_length=50, blank=True, default="")

    vehicle_number = models.CharField(max_length=50, blank=True, default="")

    remark = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_%(class)s_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class Visitor(VisitRecordBase):

    def __str__(self):
        return f"Visitor #{self.pk} - {self.person.person_name}"


class Contractor(VisitRecordBase):

    def __str__(self):
        return f"Contractor #{self.pk} - {self.person.person_name}"









# >>> Append this block to the END of models.py <<<
# (VisitorDetail and Site are defined above it in the same file)

# ban creation and update and list and delete
# One row per person per site. Banning a person at 3 sites creates 3 rows.

BAN_TYPE_CHOICES = [
    ("TEMPORARY", "TEMPORARY"),
    ("PERMANENT", "PERMANENT"),
]


class Ban(models.Model):

    guid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    person = models.ForeignKey(
        VisitorDetail,
        on_delete=models.PROTECT,
        related_name="bans"
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="bans"
    )

    ban_type = models.CharField(
        max_length=20,
        choices=BAN_TYPE_CHOICES
    )

    # TEMPORARY: both dates are required. PERMANENT: both stay null.
    from_date = models.DateField(null=True, blank=True)

    to_date = models.DateField(null=True, blank=True)

    reason = models.TextField(null=True, blank=True)

    # False = the ban was lifted by an admin
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bans"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bans"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.person.person_name} - {self.site.site_name} ({self.ban_type})"