from django.urls import path
from netbox.views.generic import ObjectChangeLogView, ObjectJournalView

from . import views
from .models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)

app_name = "netbox_fileserver"


def _model_urls(
    slug,
    name,
    list_view,
    detail_view,
    edit_view,
    delete_view,
    bulk_edit_view,
    bulk_delete_view,
    model,
):
    """Standard NetBox object URL set for one model."""
    return [
        path(f"{slug}/", list_view.as_view(), name=f"{name}_list"),
        path(f"{slug}/add/", edit_view.as_view(), name=f"{name}_add"),
        path(f"{slug}/edit/", bulk_edit_view.as_view(), name=f"{name}_bulk_edit"),
        path(f"{slug}/delete/", bulk_delete_view.as_view(), name=f"{name}_bulk_delete"),
        path(f"{slug}/<int:pk>/", detail_view.as_view(), name=name),
        path(f"{slug}/<int:pk>/edit/", edit_view.as_view(), name=f"{name}_edit"),
        path(f"{slug}/<int:pk>/delete/", delete_view.as_view(), name=f"{name}_delete"),
        path(
            f"{slug}/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name=f"{name}_changelog",
            kwargs={"model": model},
        ),
        path(
            f"{slug}/<int:pk>/journal/",
            ObjectJournalView.as_view(),
            name=f"{name}_journal",
            kwargs={"model": model},
        ),
    ]


urlpatterns = [
    *_model_urls(
        "deployments",
        "fileserverdeployment",
        views.FileServerDeploymentListView,
        views.FileServerDeploymentView,
        views.FileServerDeploymentEditView,
        views.FileServerDeploymentDeleteView,
        views.FileServerDeploymentBulkEditView,
        views.FileServerDeploymentBulkDeleteView,
        FileServerDeployment,
    ),
    *_model_urls(
        "enrollment-tokens",
        "fileserverenrollmenttoken",
        views.FileServerEnrollmentTokenListView,
        views.FileServerEnrollmentTokenView,
        views.FileServerEnrollmentTokenEditView,
        views.FileServerEnrollmentTokenDeleteView,
        views.FileServerEnrollmentTokenBulkEditView,
        views.FileServerEnrollmentTokenBulkDeleteView,
        FileServerEnrollmentToken,
    ),
    *_model_urls(
        "samba-domains",
        "sambadomain",
        views.SambaDomainListView,
        views.SambaDomainView,
        views.SambaDomainEditView,
        views.SambaDomainDeleteView,
        views.SambaDomainBulkEditView,
        views.SambaDomainBulkDeleteView,
        SambaDomain,
    ),
    *_model_urls(
        "nextcloud-instances",
        "nextcloudinstance",
        views.NextcloudInstanceListView,
        views.NextcloudInstanceView,
        views.NextcloudInstanceEditView,
        views.NextcloudInstanceDeleteView,
        views.NextcloudInstanceBulkEditView,
        views.NextcloudInstanceBulkDeleteView,
        NextcloudInstance,
    ),
    *_model_urls(
        "shares",
        "fileshare",
        views.FileShareListView,
        views.FileShareView,
        views.FileShareEditView,
        views.FileShareDeleteView,
        views.FileShareBulkEditView,
        views.FileShareBulkDeleteView,
        FileShare,
    ),
    *_model_urls(
        "domain-groups",
        "domaingroup",
        views.DomainGroupListView,
        views.DomainGroupView,
        views.DomainGroupEditView,
        views.DomainGroupDeleteView,
        views.DomainGroupBulkEditView,
        views.DomainGroupBulkDeleteView,
        DomainGroup,
    ),
]
