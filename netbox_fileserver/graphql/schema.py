import strawberry
import strawberry_django

from .types import (
    DomainGroupType,
    FileServerDeploymentType,
    FileServerEnrollmentTokenType,
    FileShareType,
    NextcloudInstanceType,
    SambaConfigFileType,
    SambaConfigSnapshotType,
    SambaDomainType,
    SambaObservedGroupType,
    SambaObservedShareType,
    SambaObservedUserType,
    SambaServerStateType,
    SambaSessionType,
    SambaSyncRunType,
)


@strawberry.type(name="Query")
class NetBoxFileServerQuery:
    fileserver_deployment: FileServerDeploymentType = strawberry_django.field()
    fileserver_deployment_list: list[FileServerDeploymentType] = strawberry_django.field()

    fileserver_enrollment_token: FileServerEnrollmentTokenType = strawberry_django.field()
    fileserver_enrollment_token_list: list[FileServerEnrollmentTokenType] = strawberry_django.field()

    samba_domain: SambaDomainType = strawberry_django.field()
    samba_domain_list: list[SambaDomainType] = strawberry_django.field()

    nextcloud_instance: NextcloudInstanceType = strawberry_django.field()
    nextcloud_instance_list: list[NextcloudInstanceType] = strawberry_django.field()

    file_share: FileShareType = strawberry_django.field()
    file_share_list: list[FileShareType] = strawberry_django.field()

    domain_group: DomainGroupType = strawberry_django.field()
    domain_group_list: list[DomainGroupType] = strawberry_django.field()

    samba_server_state: SambaServerStateType = strawberry_django.field()
    samba_server_state_list: list[SambaServerStateType] = strawberry_django.field()

    samba_config_file: SambaConfigFileType = strawberry_django.field()
    samba_config_file_list: list[SambaConfigFileType] = strawberry_django.field()

    samba_config_snapshot: SambaConfigSnapshotType = strawberry_django.field()
    samba_config_snapshot_list: list[SambaConfigSnapshotType] = strawberry_django.field()

    samba_observed_share: SambaObservedShareType = strawberry_django.field()
    samba_observed_share_list: list[SambaObservedShareType] = strawberry_django.field()

    samba_observed_user: SambaObservedUserType = strawberry_django.field()
    samba_observed_user_list: list[SambaObservedUserType] = strawberry_django.field()

    samba_observed_group: SambaObservedGroupType = strawberry_django.field()
    samba_observed_group_list: list[SambaObservedGroupType] = strawberry_django.field()

    samba_session: SambaSessionType = strawberry_django.field()
    samba_session_list: list[SambaSessionType] = strawberry_django.field()

    samba_sync_run: SambaSyncRunType = strawberry_django.field()
    samba_sync_run_list: list[SambaSyncRunType] = strawberry_django.field()
