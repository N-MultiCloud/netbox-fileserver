"""NetBox plugin template hooks — inject File Server panels on Tenant and VM
detail pages so NetBox is usable as the ops console (see PluginConfig auto-
discovery of template_content.template_extensions)."""

from netbox.plugins import PluginTemplateExtension

from .models import FileServerDeployment, NextcloudInstance, SambaDomain


class TenantFileServerPanel(PluginTemplateExtension):
    models = ["tenancy.tenant"]

    def right_page(self):
        tenant = self.context["object"]
        deployment = (
            FileServerDeployment.objects.filter(tenant=tenant)
            .select_related("backend")
            .first()
        )
        if deployment is None:
            return ""
        return self.render(
            "netbox_fileserver/inc/tenant_fileserver_panel.html",
            extra_context={
                "deployment": deployment,
                "shares": deployment.shares.all(),
            },
        )


class VirtualMachineFileServerPanel(PluginTemplateExtension):
    models = ["virtualization.virtualmachine"]

    def right_page(self):
        vm = self.context["object"]
        domain = SambaDomain.objects.filter(dc_vm=vm).select_related("deployment").first()
        nextcloud = (
            NextcloudInstance.objects.filter(vm=vm).select_related("deployment").first()
        )
        if domain is None and nextcloud is None:
            return ""
        return self.render(
            "netbox_fileserver/inc/vm_fileserver_panel.html",
            extra_context={"domain": domain, "nextcloud": nextcloud},
        )


template_extensions = (TenantFileServerPanel, VirtualMachineFileServerPanel)
