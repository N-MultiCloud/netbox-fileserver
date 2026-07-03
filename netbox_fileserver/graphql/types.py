import strawberry_django

from ..models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
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
