from django.db.models import Count
from netbox.views import generic

from .filtersets import (
    DomainGroupFilterSet,
    FileServerDeploymentFilterSet,
    FileServerEnrollmentTokenFilterSet,
    FileShareFilterSet,
    NextcloudInstanceFilterSet,
    SambaConfigFileFilterSet,
    SambaConfigSnapshotFilterSet,
    SambaDomainFilterSet,
    SambaObservedGroupFilterSet,
    SambaObservedShareFilterSet,
    SambaObservedUserFilterSet,
    SambaServerStateFilterSet,
    SambaSessionFilterSet,
    SambaSyncRunFilterSet,
)
from .forms import (
    DomainGroupBulkEditForm,
    DomainGroupFilterForm,
    DomainGroupForm,
    FileServerDeploymentBulkEditForm,
    FileServerDeploymentFilterForm,
    FileServerDeploymentForm,
    FileServerEnrollmentTokenBulkEditForm,
    FileServerEnrollmentTokenFilterForm,
    FileServerEnrollmentTokenForm,
    FileShareBulkEditForm,
    FileShareFilterForm,
    FileShareForm,
    NextcloudInstanceBulkEditForm,
    NextcloudInstanceFilterForm,
    NextcloudInstanceForm,
    SambaConfigFileBulkEditForm,
    SambaConfigFileFilterForm,
    SambaConfigFileForm,
    SambaConfigSnapshotBulkEditForm,
    SambaConfigSnapshotFilterForm,
    SambaConfigSnapshotForm,
    SambaDomainBulkEditForm,
    SambaDomainFilterForm,
    SambaDomainForm,
    SambaObservedGroupBulkEditForm,
    SambaObservedGroupFilterForm,
    SambaObservedGroupForm,
    SambaObservedShareBulkEditForm,
    SambaObservedShareFilterForm,
    SambaObservedShareForm,
    SambaObservedUserBulkEditForm,
    SambaObservedUserFilterForm,
    SambaObservedUserForm,
    SambaServerStateBulkEditForm,
    SambaServerStateFilterForm,
    SambaServerStateForm,
    SambaSessionBulkEditForm,
    SambaSessionFilterForm,
    SambaSessionForm,
    SambaSyncRunBulkEditForm,
    SambaSyncRunFilterForm,
    SambaSyncRunForm,
)
from .models import (
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
from .tables import (
    DomainGroupTable,
    FileServerDeploymentTable,
    FileServerEnrollmentTokenTable,
    FileShareTable,
    NextcloudInstanceTable,
    SambaConfigFileTable,
    SambaConfigSnapshotTable,
    SambaDomainTable,
    SambaObservedGroupTable,
    SambaObservedShareTable,
    SambaObservedUserTable,
    SambaServerStateTable,
    SambaSessionTable,
    SambaSyncRunTable,
)

# ──────────────────────── FileServerDeployment ────────────────────────


class FileServerDeploymentListView(generic.ObjectListView):
    queryset = FileServerDeployment.objects.select_related(
        "tenant", "backend", "vlan"
    ).annotate(share_count=Count("shares"))
    table = FileServerDeploymentTable
    filterset = FileServerDeploymentFilterSet
    filterset_form = FileServerDeploymentFilterForm


class FileServerDeploymentView(generic.ObjectView):
    queryset = FileServerDeployment.objects.select_related(
        "tenant", "backend", "vlan", "prefix"
    )

    def get_extra_context(self, request, instance):
        return {
            "samba_domain": getattr(instance, "samba_domain", None),
            "nextcloud_instance": getattr(instance, "nextcloud_instance", None),
            "shares_table": FileShareTable(instance.shares.all(), orderable=False),
        }


class FileServerDeploymentEditView(generic.ObjectEditView):
    queryset = FileServerDeployment.objects.all()
    form = FileServerDeploymentForm


class FileServerDeploymentDeleteView(generic.ObjectDeleteView):
    queryset = FileServerDeployment.objects.all()


class FileServerDeploymentBulkEditView(generic.BulkEditView):
    queryset = FileServerDeployment.objects.select_related("tenant", "backend", "vlan")
    filterset = FileServerDeploymentFilterSet
    table = FileServerDeploymentTable
    form = FileServerDeploymentBulkEditForm


class FileServerDeploymentBulkDeleteView(generic.BulkDeleteView):
    queryset = FileServerDeployment.objects.all()
    table = FileServerDeploymentTable


# ───────────────────── FileServerEnrollmentToken ─────────────────────


class FileServerEnrollmentTokenListView(generic.ObjectListView):
    queryset = FileServerEnrollmentToken.objects.select_related(
        "tenant", "target_deployment"
    )
    table = FileServerEnrollmentTokenTable
    filterset = FileServerEnrollmentTokenFilterSet
    filterset_form = FileServerEnrollmentTokenFilterForm


class FileServerEnrollmentTokenView(generic.ObjectView):
    queryset = FileServerEnrollmentToken.objects.select_related(
        "tenant", "target_deployment"
    )


class FileServerEnrollmentTokenEditView(generic.ObjectEditView):
    queryset = FileServerEnrollmentToken.objects.all()
    form = FileServerEnrollmentTokenForm


class FileServerEnrollmentTokenDeleteView(generic.ObjectDeleteView):
    queryset = FileServerEnrollmentToken.objects.all()


class FileServerEnrollmentTokenBulkEditView(generic.BulkEditView):
    queryset = FileServerEnrollmentToken.objects.select_related(
        "tenant", "target_deployment"
    )
    filterset = FileServerEnrollmentTokenFilterSet
    table = FileServerEnrollmentTokenTable
    form = FileServerEnrollmentTokenBulkEditForm


class FileServerEnrollmentTokenBulkDeleteView(generic.BulkDeleteView):
    queryset = FileServerEnrollmentToken.objects.all()
    table = FileServerEnrollmentTokenTable


# ──────────────────────────── SambaDomain ────────────────────────────


class SambaDomainListView(generic.ObjectListView):
    queryset = SambaDomain.objects.select_related("deployment", "dc_vm", "dc_ip")
    table = SambaDomainTable
    filterset = SambaDomainFilterSet
    filterset_form = SambaDomainFilterForm


class SambaDomainView(generic.ObjectView):
    queryset = SambaDomain.objects.select_related("deployment", "dc_vm", "dc_ip")

    def get_extra_context(self, request, instance):
        return {
            "groups_table": DomainGroupTable(instance.groups.all(), orderable=False),
        }


class SambaDomainEditView(generic.ObjectEditView):
    queryset = SambaDomain.objects.all()
    form = SambaDomainForm


class SambaDomainDeleteView(generic.ObjectDeleteView):
    queryset = SambaDomain.objects.all()


class SambaDomainBulkEditView(generic.BulkEditView):
    queryset = SambaDomain.objects.select_related("deployment")
    filterset = SambaDomainFilterSet
    table = SambaDomainTable
    form = SambaDomainBulkEditForm


class SambaDomainBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaDomain.objects.all()
    table = SambaDomainTable


# ────────────────────────── NextcloudInstance ─────────────────────────


class NextcloudInstanceListView(generic.ObjectListView):
    queryset = NextcloudInstance.objects.select_related("deployment", "vm", "ip")
    table = NextcloudInstanceTable
    filterset = NextcloudInstanceFilterSet
    filterset_form = NextcloudInstanceFilterForm


class NextcloudInstanceView(generic.ObjectView):
    queryset = NextcloudInstance.objects.select_related("deployment", "vm", "ip")


class NextcloudInstanceEditView(generic.ObjectEditView):
    queryset = NextcloudInstance.objects.all()
    form = NextcloudInstanceForm


class NextcloudInstanceDeleteView(generic.ObjectDeleteView):
    queryset = NextcloudInstance.objects.all()


class NextcloudInstanceBulkEditView(generic.BulkEditView):
    queryset = NextcloudInstance.objects.select_related("deployment")
    filterset = NextcloudInstanceFilterSet
    table = NextcloudInstanceTable
    form = NextcloudInstanceBulkEditForm


class NextcloudInstanceBulkDeleteView(generic.BulkDeleteView):
    queryset = NextcloudInstance.objects.all()
    table = NextcloudInstanceTable


# ──────────────────────────────── FileShare ───────────────────────────


class FileShareListView(generic.ObjectListView):
    queryset = FileShare.objects.select_related("deployment")
    table = FileShareTable
    filterset = FileShareFilterSet
    filterset_form = FileShareFilterForm


class FileShareView(generic.ObjectView):
    queryset = FileShare.objects.select_related("deployment")


class FileShareEditView(generic.ObjectEditView):
    queryset = FileShare.objects.all()
    form = FileShareForm


class FileShareDeleteView(generic.ObjectDeleteView):
    queryset = FileShare.objects.all()


class FileShareBulkEditView(generic.BulkEditView):
    queryset = FileShare.objects.select_related("deployment")
    filterset = FileShareFilterSet
    table = FileShareTable
    form = FileShareBulkEditForm


class FileShareBulkDeleteView(generic.BulkDeleteView):
    queryset = FileShare.objects.all()
    table = FileShareTable


# ──────────────────────────────── DomainGroup ──────────────────────────


class DomainGroupListView(generic.ObjectListView):
    queryset = DomainGroup.objects.select_related("domain")
    table = DomainGroupTable
    filterset = DomainGroupFilterSet
    filterset_form = DomainGroupFilterForm


class DomainGroupView(generic.ObjectView):
    queryset = DomainGroup.objects.select_related("domain")


class DomainGroupEditView(generic.ObjectEditView):
    queryset = DomainGroup.objects.all()
    form = DomainGroupForm


class DomainGroupDeleteView(generic.ObjectDeleteView):
    queryset = DomainGroup.objects.all()


class DomainGroupBulkEditView(generic.BulkEditView):
    queryset = DomainGroup.objects.select_related("domain")
    filterset = DomainGroupFilterSet
    table = DomainGroupTable
    form = DomainGroupBulkEditForm


class DomainGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = DomainGroup.objects.all()
    table = DomainGroupTable


# ─────────────────────────── Samba observed state ───────────────────────────


class SambaServerStateListView(generic.ObjectListView):
    queryset = SambaServerState.objects.select_related("domain")
    table = SambaServerStateTable
    filterset = SambaServerStateFilterSet
    filterset_form = SambaServerStateFilterForm


class SambaServerStateView(generic.ObjectView):
    queryset = SambaServerState.objects.select_related("domain")


class SambaServerStateEditView(generic.ObjectEditView):
    queryset = SambaServerState.objects.all()
    form = SambaServerStateForm


class SambaServerStateDeleteView(generic.ObjectDeleteView):
    queryset = SambaServerState.objects.all()


class SambaServerStateBulkEditView(generic.BulkEditView):
    queryset = SambaServerState.objects.select_related("domain")
    filterset = SambaServerStateFilterSet
    table = SambaServerStateTable
    form = SambaServerStateBulkEditForm


class SambaServerStateBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaServerState.objects.all()
    table = SambaServerStateTable


class SambaConfigFileListView(generic.ObjectListView):
    queryset = SambaConfigFile.objects.select_related("domain")
    table = SambaConfigFileTable
    filterset = SambaConfigFileFilterSet
    filterset_form = SambaConfigFileFilterForm


class SambaConfigFileView(generic.ObjectView):
    queryset = SambaConfigFile.objects.select_related("domain")


class SambaConfigFileEditView(generic.ObjectEditView):
    queryset = SambaConfigFile.objects.all()
    form = SambaConfigFileForm


class SambaConfigFileDeleteView(generic.ObjectDeleteView):
    queryset = SambaConfigFile.objects.all()


class SambaConfigFileBulkEditView(generic.BulkEditView):
    queryset = SambaConfigFile.objects.select_related("domain")
    filterset = SambaConfigFileFilterSet
    table = SambaConfigFileTable
    form = SambaConfigFileBulkEditForm


class SambaConfigFileBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaConfigFile.objects.all()
    table = SambaConfigFileTable


class SambaConfigSnapshotListView(generic.ObjectListView):
    queryset = SambaConfigSnapshot.objects.select_related("domain")
    table = SambaConfigSnapshotTable
    filterset = SambaConfigSnapshotFilterSet
    filterset_form = SambaConfigSnapshotFilterForm


class SambaConfigSnapshotView(generic.ObjectView):
    queryset = SambaConfigSnapshot.objects.select_related("domain")


class SambaConfigSnapshotEditView(generic.ObjectEditView):
    queryset = SambaConfigSnapshot.objects.all()
    form = SambaConfigSnapshotForm


class SambaConfigSnapshotDeleteView(generic.ObjectDeleteView):
    queryset = SambaConfigSnapshot.objects.all()


class SambaConfigSnapshotBulkEditView(generic.BulkEditView):
    queryset = SambaConfigSnapshot.objects.select_related("domain")
    filterset = SambaConfigSnapshotFilterSet
    table = SambaConfigSnapshotTable
    form = SambaConfigSnapshotBulkEditForm


class SambaConfigSnapshotBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaConfigSnapshot.objects.all()
    table = SambaConfigSnapshotTable


class SambaObservedShareListView(generic.ObjectListView):
    queryset = SambaObservedShare.objects.select_related("domain")
    table = SambaObservedShareTable
    filterset = SambaObservedShareFilterSet
    filterset_form = SambaObservedShareFilterForm


class SambaObservedShareView(generic.ObjectView):
    queryset = SambaObservedShare.objects.select_related("domain")


class SambaObservedShareEditView(generic.ObjectEditView):
    queryset = SambaObservedShare.objects.all()
    form = SambaObservedShareForm


class SambaObservedShareDeleteView(generic.ObjectDeleteView):
    queryset = SambaObservedShare.objects.all()


class SambaObservedShareBulkEditView(generic.BulkEditView):
    queryset = SambaObservedShare.objects.select_related("domain")
    filterset = SambaObservedShareFilterSet
    table = SambaObservedShareTable
    form = SambaObservedShareBulkEditForm


class SambaObservedShareBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaObservedShare.objects.all()
    table = SambaObservedShareTable


class SambaObservedUserListView(generic.ObjectListView):
    queryset = SambaObservedUser.objects.select_related("domain")
    table = SambaObservedUserTable
    filterset = SambaObservedUserFilterSet
    filterset_form = SambaObservedUserFilterForm


class SambaObservedUserView(generic.ObjectView):
    queryset = SambaObservedUser.objects.select_related("domain")


class SambaObservedUserEditView(generic.ObjectEditView):
    queryset = SambaObservedUser.objects.all()
    form = SambaObservedUserForm


class SambaObservedUserDeleteView(generic.ObjectDeleteView):
    queryset = SambaObservedUser.objects.all()


class SambaObservedUserBulkEditView(generic.BulkEditView):
    queryset = SambaObservedUser.objects.select_related("domain")
    filterset = SambaObservedUserFilterSet
    table = SambaObservedUserTable
    form = SambaObservedUserBulkEditForm


class SambaObservedUserBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaObservedUser.objects.all()
    table = SambaObservedUserTable


class SambaObservedGroupListView(generic.ObjectListView):
    queryset = SambaObservedGroup.objects.select_related("domain")
    table = SambaObservedGroupTable
    filterset = SambaObservedGroupFilterSet
    filterset_form = SambaObservedGroupFilterForm


class SambaObservedGroupView(generic.ObjectView):
    queryset = SambaObservedGroup.objects.select_related("domain")


class SambaObservedGroupEditView(generic.ObjectEditView):
    queryset = SambaObservedGroup.objects.all()
    form = SambaObservedGroupForm


class SambaObservedGroupDeleteView(generic.ObjectDeleteView):
    queryset = SambaObservedGroup.objects.all()


class SambaObservedGroupBulkEditView(generic.BulkEditView):
    queryset = SambaObservedGroup.objects.select_related("domain")
    filterset = SambaObservedGroupFilterSet
    table = SambaObservedGroupTable
    form = SambaObservedGroupBulkEditForm


class SambaObservedGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaObservedGroup.objects.all()
    table = SambaObservedGroupTable


class SambaSessionListView(generic.ObjectListView):
    queryset = SambaSession.objects.select_related("domain")
    table = SambaSessionTable
    filterset = SambaSessionFilterSet
    filterset_form = SambaSessionFilterForm


class SambaSessionView(generic.ObjectView):
    queryset = SambaSession.objects.select_related("domain")


class SambaSessionEditView(generic.ObjectEditView):
    queryset = SambaSession.objects.all()
    form = SambaSessionForm


class SambaSessionDeleteView(generic.ObjectDeleteView):
    queryset = SambaSession.objects.all()


class SambaSessionBulkEditView(generic.BulkEditView):
    queryset = SambaSession.objects.select_related("domain")
    filterset = SambaSessionFilterSet
    table = SambaSessionTable
    form = SambaSessionBulkEditForm


class SambaSessionBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaSession.objects.all()
    table = SambaSessionTable


class SambaSyncRunListView(generic.ObjectListView):
    queryset = SambaSyncRun.objects.select_related("domain")
    table = SambaSyncRunTable
    filterset = SambaSyncRunFilterSet
    filterset_form = SambaSyncRunFilterForm


class SambaSyncRunView(generic.ObjectView):
    queryset = SambaSyncRun.objects.select_related("domain")


class SambaSyncRunEditView(generic.ObjectEditView):
    queryset = SambaSyncRun.objects.all()
    form = SambaSyncRunForm


class SambaSyncRunDeleteView(generic.ObjectDeleteView):
    queryset = SambaSyncRun.objects.all()


class SambaSyncRunBulkEditView(generic.BulkEditView):
    queryset = SambaSyncRun.objects.select_related("domain")
    filterset = SambaSyncRunFilterSet
    table = SambaSyncRunTable
    form = SambaSyncRunBulkEditForm


class SambaSyncRunBulkDeleteView(generic.BulkDeleteView):
    queryset = SambaSyncRun.objects.all()
    table = SambaSyncRunTable
