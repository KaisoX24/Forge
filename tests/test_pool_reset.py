from sandbox.container_pool import ContainerPool
from sandbox.sandbox import SandBox


class FakeContainer:
    def __init__(self, find_code=0, processes=1, top_raises=False, run_output=b"ok"):
        self.find_code, self.processes, self.top_raises, self.run_output = find_code, processes, top_raises, run_output
        self.removed = False

    def exec_run(self, cmd):
        return (self.find_code, b"") if cmd[0] == "find" else (0, self.run_output)

    def top(self):
        if self.top_raises:
            raise RuntimeError("daemon hiccup")
        return {"Processes": [["x"]] * self.processes}

    def remove(self, force=False):
        self.removed = True


reset = ContainerPool.reset


def test_clean_container_is_reusable():
    assert reset(None, FakeContainer()) is True


def test_leftover_background_process_taints_the_container():
    assert reset(None, FakeContainer(processes=2)) is False


def test_failed_wipe_taints_the_container():
    assert reset(None, FakeContainer(find_code=1)) is False


def test_daemon_error_during_reset_taints_instead_of_raising():
    assert reset(None, FakeContainer(top_raises=True)) is False


class FakePool:
    def __init__(self, container, reusable):
        self.container, self.reusable = container, reusable
        self.returned, self.replaced = [], 0

    def get_container(self): return self.container
    def reset(self, c): return self.reusable
    def return_container(self, c): self.returned.append(c)
    def replace_container(self): self.replaced += 1


def test_sandbox_returns_a_clean_container_to_the_pool():
    pool = FakePool(FakeContainer(), reusable=True)
    assert SandBox(pool, "print(1)").sandbox_instance().success
    assert pool.returned == [pool.container] and pool.replaced == 0 and not pool.container.removed


def test_sandbox_discards_and_replaces_a_tainted_container():
    pool = FakePool(FakeContainer(), reusable=False)
    SandBox(pool, "print(1)").sandbox_instance()
    assert pool.returned == [] and pool.replaced == 1 and pool.container.removed