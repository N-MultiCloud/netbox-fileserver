import strawberry_django

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
class FileServerDeploymentType:
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
class FileServerEnrollmentTokenType:
    pass


@strawberry_django.type(SambaDomain, fields="__all__")
class SambaDomainType:
    pass


@strawberry_django.type(NextcloudInstance, fields="__all__")
class NextcloudInstanceType:
    pass


@strawberry_django.type(FileShare, fields="__all__")
class FileShareType:
    pass


@strawberry_django.type(DomainGroup, fields="__all__")
class DomainGroupType:
    pass


@strawberry_django.type(SambaServerState, fields="__all__")
class SambaServerStateType:
    pass


@strawberry_django.type(SambaConfigFile, fields="__all__")
class SambaConfigFileType:
    pass


@strawberry_django.type(SambaConfigSnapshot, fields="__all__")
class SambaConfigSnapshotType:
    pass


@strawberry_django.type(SambaObservedShare, fields="__all__")
class SambaObservedShareType:
    pass


@strawberry_django.type(SambaObservedUser, fields="__all__")
class SambaObservedUserType:
    pass


@strawberry_django.type(SambaObservedGroup, fields="__all__")
class SambaObservedGroupType:
    pass


@strawberry_django.type(SambaSession, fields="__all__")
class SambaSessionType:
    pass


@strawberry_django.type(SambaSyncRun, fields="__all__")
class SambaSyncRunType:
    pass
