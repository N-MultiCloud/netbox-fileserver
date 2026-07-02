from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_fileserver"

router = NetBoxRouter()
router.register("deployments", views.FileServerDeploymentViewSet)
router.register("samba-domains", views.SambaDomainViewSet)
router.register("nextcloud-instances", views.NextcloudInstanceViewSet)
router.register("shares", views.FileShareViewSet)
router.register("domain-groups", views.DomainGroupViewSet)

urlpatterns = router.urls
