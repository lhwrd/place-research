"""Baserow webhook receiver: queues enrichment for new and re-enrich rows."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api import deps
from app.core.config import settings
from app.schemas.listing import BaserowWebhookPayload
from app.services.baserow_enrichment import (
    BaserowEnrichmentService,
    get_baserow_service,
    needs_enrichment,
    row_status,
)

router = APIRouter(dependencies=[Depends(deps.verify_baserow_webhook)])
logger = logging.getLogger(__name__)

ROW_EVENTS = ("rows.created", "rows.updated")


@router.post(
    "/baserow",
    status_code=status.HTTP_200_OK,
    summary="Baserow row webhook",
    description="Receives rows.created / rows.updated events for the Properties table",
)
async def baserow_webhook(
    payload: BaserowWebhookPayload,
    background_tasks: BackgroundTasks,
    service: BaserowEnrichmentService = Depends(get_baserow_service),
):
    """
    Queue enrichment for rows whose Status is New, Re-enrich or empty.

    Responds immediately; Baserow times out slow webhooks. Rows in other states (including
    the Enriching/Enriched/Error updates this service makes itself) are ignored.
    """
    if payload.event_type not in ROW_EVENTS or (
        payload.table_id is not None and payload.table_id != settings.baserow_properties_table_id
    ):
        return {"queued": []}

    queued = [
        item["id"] for item in payload.items if "id" in item and needs_enrichment(row_status(item))
    ]
    for row_id in queued:
        background_tasks.add_task(_enrich_safely, service, row_id)

    if queued:
        logger.info("Queued enrichment for Baserow rows %s", queued)
    return {"queued": queued}


async def _enrich_safely(service: BaserowEnrichmentService, row_id: int) -> None:
    # Background task errors would otherwise only surface as an ASGI traceback
    try:
        await service.enrich_row(row_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Background enrichment failed for row %s: %s", row_id, e, exc_info=True)
