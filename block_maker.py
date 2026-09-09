

from __future__ import annotations

import itertools
from typing import List, Optional, Tuple

from app.models.schemas import (
    Block,
    MaintenanceRequest,
    PlanningCalendar,
    UnplacedRequest,
)
from app.services.compatibility import feasible_blocks

_new_block_counter = itertools.count(1)


def _next_new_block_id(existing_ids: set) -> str:
    while True:
        candidate = f"NEWBLK-{next(_new_block_counter):04d}"
        if candidate not in existing_ids:
            return candidate


def find_matching_block(
    request: MaintenanceRequest, blocks: List[Block]
) -> Optional[Block]:
    """Returns the first existing block the request feasibly fits into, or None."""
    candidates = feasible_blocks(request, blocks)
    return candidates[0] if candidates else None


def merge_request_into_block(request: MaintenanceRequest, block: Block) -> Block:
    """Merges a request into a block in place, updating usage and resource lists."""
    block.used_duration_hrs = round(
        block.used_duration_hrs + request.estimated_duration_hrs, 4
    )
    block.merged_request_ids.append(request.request_id)

    merged_resources = set(block.assigned_resources) | set(request.required_resources)
    block.assigned_resources = sorted(merged_resources)

    return block


def create_new_block(
    request: MaintenanceRequest,
    calendar: PlanningCalendar,
    existing_block_ids: set,
) -> Block:
   
    block_start = max(request.earliest_start, calendar.start_date)
    block_end = min(request.latest_end, calendar.end_date)

    new_id = _next_new_block_id(existing_block_ids)
    existing_block_ids.add(new_id)

    return Block(
        block_id=new_id,
        section_id=request.section_id,
        track_id=request.track_id,
        block_start=block_start,
        block_end=block_end,
        allocated_duration_hrs=request.estimated_duration_hrs,
        used_duration_hrs=request.estimated_duration_hrs,
        assigned_resources=sorted(request.required_resources),
        merged_request_ids=[request.request_id],
        is_new=True,
    )


def process_requests(
    requests: List[MaintenanceRequest],
    existing_blocks: List[Block],
    calendar: PlanningCalendar,
) -> Tuple[List[Block], List[UnplacedRequest]]:
   
    blocks: List[Block] = list(existing_blocks)
    existing_block_ids = {b.block_id for b in blocks}
    unplaced: List[UnplacedRequest] = []

    for request in requests:
        try:
            match = find_matching_block(request, blocks)
            if match is not None:
                merge_request_into_block(request, match)
            else:
                new_block = create_new_block(request, calendar, existing_block_ids)
                blocks.append(new_block)
        except Exception as exc:  # noqa: BLE001 - surface as an unplaced reason
            unplaced.append(UnplacedRequest(request_id=request.request_id, reason=str(exc)))

    return blocks, unplaced
