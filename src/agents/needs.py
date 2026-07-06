from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Needs:
    """Agent-local hunger state. All timing is in sim seconds."""

    def __init__(self):
        self.hunger: float = 1.0          # 1=full, 0=starving
        self.starvation_timer: float = 0.0
        self.eat_retry_timer: float = 0.0  # cooldown after failing to find bread
        self.is_dead: bool = False

    def update(self, dt: float) -> None:
        from src.core import config

        self.hunger = max(0.0, self.hunger - config.HUNGER_DECAY_PER_SECOND * dt)

        if self.eat_retry_timer > 0.0:
            self.eat_retry_timer = max(0.0, self.eat_retry_timer - dt)

        if self.hunger == 0.0:
            self.starvation_timer += dt
            if self.starvation_timer >= config.STARVATION_GRACE_PERIOD:
                self.is_dead = True
        else:
            self.starvation_timer = 0.0

    @property
    def speed_multiplier(self) -> float:
        """0.6× speed below critical threshold — visible desperation."""
        from src.core import config
        if self.hunger < config.HUNGER_CRITICAL_THRESHOLD:
            return 0.6
        return 1.0
