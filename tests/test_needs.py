"""Unit tests for the Needs component (hunger decay, starvation, speed)."""
from src.agents.needs import Needs
from src.core import config


def test_hunger_decays_at_configured_rate():
    needs = Needs()
    assert needs.hunger == 1.0
    dt = 1.0
    needs.update(dt)
    expected = 1.0 - config.HUNGER_DECAY_PER_SECOND * dt
    assert abs(needs.hunger - expected) < 1e-9


def test_hunger_clamped_at_zero():
    needs = Needs()
    needs.hunger = 0.001
    needs.update(10.0)  # large dt
    assert needs.hunger == 0.0


def test_starvation_timer_only_ticks_at_zero():
    needs = Needs()
    needs.hunger = 0.1
    needs.update(1.0)
    assert needs.starvation_timer == 0.0

    needs.hunger = 0.0
    needs.update(5.0)
    assert needs.starvation_timer == 5.0


def test_agent_dies_after_grace_period():
    needs = Needs()
    needs.hunger = 0.0
    assert not needs.is_dead
    needs.update(config.STARVATION_GRACE_PERIOD + 0.1)
    assert needs.is_dead


def test_speed_multiplier_below_critical():
    needs = Needs()
    needs.hunger = config.HUNGER_CRITICAL_THRESHOLD - 0.01
    assert needs.speed_multiplier == 0.6


def test_speed_multiplier_above_critical():
    needs = Needs()
    needs.hunger = config.HUNGER_CRITICAL_THRESHOLD + 0.01
    assert needs.speed_multiplier == 1.0


def test_eat_retry_timer_decrements():
    needs = Needs()
    needs.eat_retry_timer = 5.0
    needs.update(2.0)
    assert abs(needs.eat_retry_timer - 3.0) < 1e-9
    needs.update(10.0)
    assert needs.eat_retry_timer == 0.0
