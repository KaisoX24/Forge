import threading
from collections import OrderedDict
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass

from api.services.grader.grader import Grader
from models.data_models import EnvironmentSpec
from sandbox import ContainerPool

@dataclass
class _Entry:
    stack:ExitStack
    pool:object
    grader:Grader

class GraderRegistry:
    """One sandbox pool per course, because each course has its own environment image."""

    def __init__(self,*,max_pools:int=1,
                 pool_size:int=2,
                 pool_factory:Callable[[EnvironmentSpec,int],object]|None=None,
                 grader_factory:Callable[[object],Grader]=Grader.from_pool):

        self._max_pools=max_pools
        self._pool_size=pool_size
        self._make_pool=pool_factory or (lambda spec,size:ContainerPool(pool_size=size,spec=spec))
        self._make_grader=grader_factory
        self._entries:OrderedDict[str,_Entry]=OrderedDict()
        self._lock=threading.Lock()

    def _entry(self, course_key: str, env: EnvironmentSpec) -> _Entry:
        with self._lock:
            entry = self._entries.get(course_key)
            if entry is not None:
                self._entries.move_to_end(course_key)
                return entry
            while len(self._entries) >= self._max_pools:
                _, oldest = self._entries.popitem(last=False)
                oldest.stack.close()
            stack = ExitStack()
            try:
                pool = stack.enter_context(self._make_pool(env, self._pool_size))
                grader = self._make_grader(pool)
            except BaseException:
                stack.close()
                raise
            entry = _Entry(stack, pool, grader)
            self._entries[course_key] = entry
            return entry

    def for_course(self,course_key:str,env:EnvironmentSpec) ->Grader:
        return self._entry(course_key,env).grader

    def pool_for(self, course_key: str, env: EnvironmentSpec) -> object:
        return self._entry(course_key, env).pool

    def close(self) -> None:
        with self._lock:
            while self._entries:
                _,entry=self._entries.popitem(last=False)
                entry.stack.close()