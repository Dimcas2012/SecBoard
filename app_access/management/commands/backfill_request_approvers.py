from django.core.management.base import BaseCommand
from django.db import transaction

from app_access.models import (
    AccessRequest,
    AccessRequestApprover,
)


class Command(BaseCommand):
    help = "Backfill AccessRequestApprover records for legacy Access Requests that have none."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=int,
            help="Limit backfill to a specific company ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write changes, only report what would be done",
        )

    def handle(self, *args, **options):
        company_id = options.get("company_id")
        dry_run = options.get("dry_run")

        qs = AccessRequest.objects.all()
        if company_id:
            qs = qs.filter(company_id=company_id)

        qs = qs.filter(request_approvers__isnull=True).distinct()

        total = qs.count()
        created_total = 0

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No requests require backfill."))
            return

        self.stdout.write(f"Found {total} access request(s) missing approvers. Starting backfill...")

        for req in qs.iterator():
            try:
                with transaction.atomic():
                    # Choose source approvers: prefer the first access_record approvers; fallback to system approvers
                    source_approvers = []
                    access_record = req.access_records.first()
                    if access_record:
                        source_approvers = list(access_record.approvers.all().order_by("order"))
                    if not source_approvers and hasattr(req.system, "approving_persons"):
                        source_approvers = list(req.system.approving_persons.all().order_by("order"))

                    if not source_approvers:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Request {req.id}: no source approvers found; skipping"
                            )
                        )
                        continue

                    created = 0
                    for sa in source_approvers:
                        cabinet_user = getattr(sa, "cabinet_user", None)
                        order = getattr(sa, "order", 1)
                        if not cabinet_user:
                            continue

                        if dry_run:
                            created += 1
                            continue

                        AccessRequestApprover.objects.get_or_create(
                            access_request=req,
                            cabinet_user=cabinet_user,
                            defaults={
                                "access_approver": sa if sa._meta.model_name == "accessapprover" else None,
                                "order": order,
                                # If the whole request is already approved, mark approvers approved; else leave pending
                                "current_status": "approved" if req.status == "approved" else "pending",
                            },
                        )
                        created += 1

                    created_total += created
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Request {req.id}: backfilled {created} approver(s)"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed backfilling request {req.id}: {e}"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run complete. Would create {created_total} approver rows across {total} request(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Backfill complete. Created/ensured approvers for {total} request(s)."
                )
            )


