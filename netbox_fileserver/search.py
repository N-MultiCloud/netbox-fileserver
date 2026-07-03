from netbox.search import SearchIndex, register_search

from .models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)


@register_search
class FileServerDeploymentIndex(SearchIndex):
    model = FileServerDeployment
    fields = (
        ("fqdn", 100),
        ("secret_ref", 400),
        ("description", 500),
    )


@register_search
class FileServerEnrollmentTokenIndex(SearchIndex):
    model = FileServerEnrollmentToken
    fields = (
        ("token_hash", 500),
    )


@register_search
class SambaDomainIndex(SearchIndex):
    model = SambaDomain
    fields = (
        ("realm", 100),
        ("netbios_name", 150),
    )


@register_search
class NextcloudInstanceIndex(SearchIndex):
    model = NextcloudInstance
    fields = (
        ("version", 300),
        ("ldap_config_id", 400),
    )


@register_search
class FileShareIndex(SearchIndex):
    model = FileShare
    fields = (
        ("name", 100),
        ("path", 200),
        ("nc_mount_point", 300),
        ("description", 500),
    )


@register_search
class DomainGroupIndex(SearchIndex):
    model = DomainGroup
    fields = (
        ("name", 100),
        ("description", 500),
    )
