from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_fileserver"

router = NetBoxRouter()
router.register("deployments", views.FileServerDeploymentViewSet)
router.register("enrollment-tokens", views.FileServerEnrollmentTokenViewSet)
router.register("samba-domains", views.SambaDomainViewSet)
router.register("nextcloud-instances", views.NextcloudInstanceViewSet)
router.register("shares", views.FileShareViewSet)
router.register("domain-groups", views.DomainGroupViewSet)
router.register("samba-server-states", views.SambaServerStateViewSet)
router.register("samba-config-files", views.SambaConfigFileViewSet)
router.register("samba-config-snapshots", views.SambaConfigSnapshotViewSet)
router.register("samba-observed-shares", views.SambaObservedShareViewSet)
router.register("samba-observed-users", views.SambaObservedUserViewSet)
router.register("samba-observed-groups", views.SambaObservedGroupViewSet)
router.register("samba-sessions", views.SambaSessionViewSet)
router.register("samba-sync-runs", views.SambaSyncRunViewSet)

urlpatterns = router.urls
