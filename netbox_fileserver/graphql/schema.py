import strawberry
import strawberry_django

from .types import (
    DomainGroupType,
    FileServerDeploymentType,
    FileShareType,
    NextcloudInstanceType,
    SambaDomainType,
)


@strawberry.type(name="Query")
class NetBoxFileServerQuery:
    fileserver_deployment: FileServerDeploymentType = strawberry_django.field()
    fileserver_deployment_list: list[FileServerDeploymentType] = strawberry_django.field()

    samba_domain: SambaDomainType = strawberry_django.field()
    samba_domain_list: list[SambaDomainType] = strawberry_django.field()

    nextcloud_instance: NextcloudInstanceType = strawberry_django.field()
    nextcloud_instance_list: list[NextcloudInstanceType] = strawberry_django.field()

    file_share: FileShareType = strawberry_django.field()
    file_share_list: list[FileShareType] = strawberry_django.field()

    domain_group: DomainGroupType = strawberry_django.field()
    domain_group_list: list[DomainGroupType] = strawberry_django.field()
