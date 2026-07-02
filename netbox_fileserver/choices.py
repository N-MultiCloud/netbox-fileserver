from utilities.choices import ChoiceSet


class DeploymentStatusChoices(ChoiceSet):
    """Lifecycle status shared by every file-server object.

    The reconciler (NMS file-server backend) drives an object from ``planned``
    through ``provisioning`` to ``active``, writing the observed status back so
    the NetBox UI and the portal read the same truth.
    """

    STATUS_PLANNED = "planned"
    STATUS_PROVISIONING = "provisioning"
    STATUS_ACTIVE = "active"
    STATUS_DEGRADED = "degraded"
    STATUS_FAILED = "failed"
    STATUS_DECOMMISSIONING = "decommissioning"
    STATUS_DECOMMISSIONED = "decommissioned"

    CHOICES = [
        (STATUS_PLANNED, "Planned", "gray"),
        (STATUS_PROVISIONING, "Provisioning", "cyan"),
        (STATUS_ACTIVE, "Active", "green"),
        (STATUS_DEGRADED, "Degraded", "orange"),
        (STATUS_FAILED, "Failed", "red"),
        (STATUS_DECOMMISSIONING, "Decommissioning", "yellow"),
        (STATUS_DECOMMISSIONED, "Decommissioned", "gray"),
    ]


class ACLRoleChoices(ChoiceSet):
    """Access role granted to an AD group inside a share's ``acl_spec``."""

    ROLE_READ = "ro"
    ROLE_READ_WRITE = "rw"
    ROLE_FULL = "full"
    ROLE_DENY = "deny"

    CHOICES = [
        (ROLE_READ, "Read-only", "blue"),
        (ROLE_READ_WRITE, "Read/Write", "green"),
        (ROLE_FULL, "Full control", "purple"),
        (ROLE_DENY, "Deny", "red"),
    ]


class SambaFunctionalLevelChoices(ChoiceSet):
    """AD domain/forest functional level for a Samba AD/DC."""

    LEVEL_2008_R2 = "2008_R2"
    LEVEL_2012 = "2012"
    LEVEL_2012_R2 = "2012_R2"
    LEVEL_2016 = "2016"

    CHOICES = [
        (LEVEL_2008_R2, "2008 R2"),
        (LEVEL_2012, "2012"),
        (LEVEL_2012_R2, "2012 R2"),
        (LEVEL_2016, "2016"),
    ]
