import strawberry_django
from netbox.graphql.types import NetBoxObjectType

from ..models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaConfigFile,
    SambaConfigSnapshot,
    SambaDomain,
    SambaObservedGroup,
    SambaObservedShare,
    SambaObservedUser,
    SambaServerState,
    SambaSession,
    SambaSyncRun,
)


@strawberry_django.type(FileServerDeployment, fields="__all__")
class FileServerDeploymentType(NetBoxObjectType):
    pass


@strawberry_django.type(
    FileServerEnrollmentToken,
    fields=(
        "id",
        "tenant",
        "target_deployment",
        "expires_at",
        "used_at",
        "created",
        "last_updated",
    ),
)
class FileServerEnrollmentTokenType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaDomain, fields="__all__")
class SambaDomainType(NetBoxObjectType):
    pass


@strawberry_django.type(NextcloudInstance, fields="__all__")
class NextcloudInstanceType(NetBoxObjectType):
    pass


@strawberry_django.type(FileShare, fields="__all__")
class FileShareType(NetBoxObjectType):
    pass


@strawberry_django.type(DomainGroup, fields="__all__")
class DomainGroupType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaServerState, fields="__all__")
class SambaServerStateType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaConfigFile, fields="__all__")
class SambaConfigFileType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaConfigSnapshot, fields="__all__")
class SambaConfigSnapshotType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaObservedShare, fields="__all__")
class SambaObservedShareType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaObservedUser, fields="__all__")
class SambaObservedUserType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaObservedGroup, fields="__all__")
class SambaObservedGroupType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaSession, fields="__all__")
class SambaSessionType(NetBoxObjectType):
    pass


@strawberry_django.type(SambaSyncRun, fields="__all__")
class SambaSyncRunType(NetBoxObjectType):
    pass
