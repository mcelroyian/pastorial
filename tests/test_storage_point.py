import uuid

import pygame

from src.resources.storage_point import StoragePoint
from src.resources.resource_types import ResourceType


def _sp(capacity=20, types=None):
    return StoragePoint(
        position=pygame.math.Vector2(0, 0),
        overall_capacity=capacity,
        accepted_resource_types=types,
    )


def test_add_resource_within_capacity():
    sp = _sp(capacity=10, types=[ResourceType.BERRY])
    added = sp.add_resource(ResourceType.BERRY, 5)
    assert added == 5
    assert sp.get_current_load() == 5


def test_add_resource_caps_at_capacity():
    sp = _sp(capacity=5, types=[ResourceType.BERRY])
    sp.add_resource(ResourceType.BERRY, 5)
    added = sp.add_resource(ResourceType.BERRY, 1)
    assert added == 0
    assert sp.get_current_load() == 5


def test_rejected_type_not_stored():
    sp = _sp(capacity=20, types=[ResourceType.BERRY])
    added = sp.add_resource(ResourceType.WHEAT, 3)
    assert added == 0
    assert sp.get_current_load() == 0


def test_reserve_reduces_available_capacity():
    sp = _sp(capacity=10, types=[ResourceType.BERRY])
    task_id = uuid.uuid4()
    reserved = sp.reserve_space(task_id, ResourceType.BERRY, 7)
    assert reserved == 7
    assert sp.get_available_capacity_for_reservation() == 3


def test_release_reservation_restores_capacity():
    sp = _sp(capacity=10, types=[ResourceType.BERRY])
    task_id = uuid.uuid4()
    sp.reserve_space(task_id, ResourceType.BERRY, 7)
    result = sp.release_reservation(task_id)
    assert result is True
    assert task_id not in sp.reservations
    assert sp.get_available_capacity_for_reservation() == 10


def test_commit_reservation_to_storage():
    sp = _sp(capacity=10, types=[ResourceType.BERRY])
    task_id = uuid.uuid4()
    sp.reserve_space(task_id, ResourceType.BERRY, 5)
    committed = sp.commit_reservation_to_storage(task_id, ResourceType.BERRY, 5)
    assert committed == 5
    assert sp.stored_resources.get(ResourceType.BERRY, 0) == 5
    assert task_id not in sp.reservations  # reservation consumed


def test_reserve_rejected_type_returns_zero():
    sp = _sp(capacity=20, types=[ResourceType.BERRY])
    task_id = uuid.uuid4()
    reserved = sp.reserve_space(task_id, ResourceType.WHEAT, 5)
    assert reserved == 0
    assert task_id not in sp.reservations


def test_reserve_for_pickup_and_collect():
    sp = _sp(capacity=20, types=[ResourceType.BERRY])
    sp.stored_resources[ResourceType.BERRY] = 8
    task_id = uuid.uuid4()
    reserved = sp.reserve_for_pickup(task_id, ResourceType.BERRY, 5)
    assert reserved == 5
    collected = sp.collect_reserved_pickup(task_id, ResourceType.BERRY, max_quantity_agent_can_carry=10)
    assert collected == 5
    assert sp.stored_resources.get(ResourceType.BERRY, 0) == 3  # 8 - 5


def test_release_pickup_reservation_keeps_stock():
    sp = _sp(capacity=20, types=[ResourceType.BERRY])
    sp.stored_resources[ResourceType.BERRY] = 5
    task_id = uuid.uuid4()
    sp.reserve_for_pickup(task_id, ResourceType.BERRY, 3)
    released = sp.release_pickup_reservation(task_id)
    assert released is True
    assert task_id not in sp.pickup_reservations
    assert sp.stored_resources.get(ResourceType.BERRY, 0) == 5  # stock unchanged
