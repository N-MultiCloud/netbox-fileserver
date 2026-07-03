from django.db.models import Count
from netbox.views import generic

from .filtersets import (
    DomainGroupFilterSet,
    FileServerDeploymentFilterSet,
    FileServerEnrollmentTokenFilterSet,
    FileShareFilterSet,
    NextcloudInstanceFilterSet,
    SambaDomainFilterSet,
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
    SambaDomainBulkEditForm,
    SambaDomainFilterForm,
    SambaDomainForm,
)
from .models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)
from .tables import (
    DomainGroupTable,
    FileServerDeploymentTable,
    FileServerEnrollmentTokenTable,
    FileShareTable,
    NextcloudInstanceTable,
    SambaDomainTable,
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
