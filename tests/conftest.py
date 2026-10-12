import numpy as np
import pytest

from wfg.csi.simulator import Room


@pytest.fixture
def rng():
    return np.random.default_rng(0)


@pytest.fixture
def room():
    return Room.from_seed("test_room")
